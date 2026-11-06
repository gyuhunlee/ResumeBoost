"""Decides whether an email is about a job application, and what it says.

Three stages:
1. prefilter()  free keyword/sender check that drops ~95% of an inbox
2. extract      rule-based company/role/status with evidence (extract.py)
3. classify()   LLM (Gemini) reads the email WITH those hints; its answer is
                then checked against the email, and any field it got wrong
                (e.g. the recruiter's name as the company) is replaced by
                the rule-based value. Without an API key, rules alone decide.
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from email.utils import parseaddr

import httpx

from ..config import settings
from .extract import (
    ATS_DOMAINS,
    JOB_BOARD_DOMAINS,
    clean_body,
    company_candidates,
    company_supported,
    extract_company,
    extract_role,
    extract_status,
    is_bad_company,
    is_vendor_domain,
    role_ok,
    sender_parts,
    strong_status,
)

log = logging.getLogger(__name__)

SUBJECT_HINTS = re.compile(
    r"application|applying|applied|your candidacy|interview|next steps|unfortunately|"
    r"thank you for your interest|regarding your|offer letter|job offer|assessment|"
    r"coding challenge|position|role at|exam(ination)?|eligib",
    re.I,
)

# Job boards send lots of "jobs you may like" mail that mentions roles but isn't an application.
NOISE = re.compile(r"jobs? (alert|recommendation)|recommended jobs|new jobs for you|"
                   r"is hiring|apply now|jobs you might|newsletter|webinar|jobs? (near|for) you|"
                   r"people (also )?viewed|similar jobs|top job picks|saved (search|job)", re.I)

SKIP_LABELS = {"CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL", "SPAM", "TRASH", "SENT", "DRAFT"}

# Gmail search used for the first (backfill) sync, so we only list likely emails.
BACKFILL_QUERY = (
    "-category:promotions -category:social "
    "{from:(" + " OR ".join(ATS_DOMAINS) + ") "
    'OR subject:(application OR applying OR applied OR interview OR "next steps" '
    'OR unfortunately OR "thank you for your interest" OR offer OR assessment OR examination)}'
)


def sender_domain(sender: str) -> str:
    return parseaddr(sender)[1].rpartition("@")[2].lower()


# Mailbox names that a person doesn't reply from.
_AUTOMATED_LOCAL = re.compile(
    r"^(no-?reply|do-?not-?reply|donotreply|notifications?|notify|alerts?|mailer|"
    r"auto(mated|-?confirm)?|system|jobs|careers|recruiting|talent|hiring|hr|"
    r"applications?|apply|candidates?|info|support|team)([+._-].*)?$", re.I)


def is_automated_sender(sender: str) -> bool:
    """True for ATS/job-board mail and no-reply style addresses; False when a person likely wrote it."""
    _, local, domain = sender_parts(sender)
    if is_vendor_domain(domain):
        return True
    return bool(_AUTOMATED_LOCAL.match(local))


def prefilter(sender: str, subject: str, labels: list[str]) -> bool:
    if SKIP_LABELS & set(labels):
        return False
    if NOISE.search(subject):
        return False
    domain = sender_domain(sender)
    from_ats = any(domain == d or domain.endswith("." + d) for d in ATS_DOMAINS)
    return from_ats or bool(SUBJECT_HINTS.search(subject))


@dataclass
class Classification:
    is_job_related: bool
    type: str  # applied | interviewing | offer | rejected | other
    company: str
    role: str
    confidence: float
    interview_at: datetime | None = None
    from_recruiter: bool = False  # written by a person (recruiter/hiring manager), not an automated system


PROMPT = """You extract facts from one email for a job-application tracker.

First decide if this email is from an employer (or its recruiting system) about
an application the recipient SUBMITTED. Job alerts, newsletters, marketing,
and cold outreach about jobs they never applied to are NOT.

Rules for "company" (the HIRING organization):
- NEVER the sender's personal name. "Jane Kim <jane@acme.com>" → the company is Acme, not Jane Kim.
- NEVER the ATS or job board that delivered the email (Greenhouse, Lever, Workday,
  iCIMS, LinkedIn, Indeed, NEOGOV/GovernmentJobs, ...). Look for who is hiring.
- Prefer the name as written in the email body or signature ("City of Davis", "Northwind Health").
- Government employers: use the agency name, e.g. "City of Davis", "Sacramento County".
- If you can't tell, return "".

Rules for "role": the exact job title as written, without req IDs, locations or
"position"/"role" (e.g. "Wastewater Treatment Plant Operator-in-Training"). "" if not stated.

Rules for "type":
- applied: confirmation that the application was received/submitted.
- interviewing: an actual invitation to interview, schedule a call, or take an
  assessment/exam. A confirmation that only says "if selected, we will contact you
  for an interview" is "applied", not "interviewing".
- offer: a job offer.
- rejected: not moving forward / position filled / not selected.
- other: job-related but none of these.

Hints found by a rule-based parser (may be wrong; verify against the email):
{hints}

Return JSON only:
{{"is_job_related": bool,
  "type": "applied" | "interviewing" | "offer" | "rejected" | "other",
  "company": string,
  "company_evidence": "the exact words in the email that name the company",
  "role": string,
  "interview_at": "ISO 8601 datetime with offset if a specific interview time is given, else null",
  "from_recruiter": "true if a real person (recruiter, hiring manager) wrote this to the recipient personally; false for automated/templated system mail",
  "confidence": number 0-1}}

Email received: {received}
From: {sender}
Subject: {subject}
Body:
{body}"""


def classify(sender: str, subject: str, body: str, received: datetime) -> Classification:
    body = clean_body(body)
    rules = _classify_rules(sender, subject, body)
    c = None
    if settings.gemini_api_key:
        try:
            c = _classify_llm(sender, subject, body, received, rules)
        except Exception as e:  # network error, quota, bad JSON → don't lose the email
            log.warning("LLM classify failed, using rules: %s", e)
    c = _reconcile(c, rules, sender, subject, body) if c else rules
    # A no-reply/ATS address is never a person, whatever the model thinks.
    if is_automated_sender(sender):
        c.from_recruiter = False
    return c


def _reconcile(llm: Classification, rules: Classification,
               sender: str, subject: str, body: str) -> Classification:
    """Keep the model's answer, but replace any field the email doesn't support."""
    # Company: must not be a person/vendor/generic word and must be backed by the email.
    if not company_supported(llm.company, sender, subject, body):
        if llm.company:
            log.info("LLM company %r not supported by the email; using %r", llm.company, rules.company)
        llm.company = rules.company
    # Role: must look like a job title.
    if not role_ok(llm.role, llm.company):
        llm.role = rules.role if role_ok(rules.role, llm.company) else ""
    # Status: an explicit rejection/offer in the text beats a model's "applied".
    plain = strong_status(subject, body)
    if plain and llm.type in {"applied", "other"}:
        llm.type = plain
    if llm.type == "other" and rules.type != "other":
        llm.type = rules.type
    if not llm.company:
        llm.is_job_related = False
    return llm


def _hints(sender: str, subject: str, body: str, rules: Classification) -> str:
    name, _, domain = sender_parts(sender)
    lines = []
    if is_vendor_domain(domain):
        kind = "job board" if any(domain.endswith(d) for d in JOB_BOARD_DOMAINS) else "ATS (applicant tracking system)"
        lines.append(f"- The sender domain {domain} belongs to an {kind}, NOT the employer.")
    if name and is_bad_company(name, sender):
        lines.append(f"- The sender display name \"{name}\" is a person or vendor, NOT the company.")
    cands = company_candidates(sender, subject, body)[:3]
    if cands:
        lines.append("- Company candidates: " + ", ".join(f"{c.name} ({'/'.join(c.sources)})" for c in cands))
    if rules.role:
        lines.append(f"- Role candidate: {rules.role}")
    if rules.type != "other":
        lines.append(f"- Status candidate: {rules.type}")
    return "\n".join(lines) or "- none"


def _classify_llm(sender: str, subject: str, body: str, received: datetime,
                  rules: Classification) -> Classification:
    prompt = PROMPT.format(received=received.isoformat(), sender=sender, subject=subject,
                           body=body[:3000], hints=_hints(sender, subject, body, rules))
    r = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent",
        headers={"x-goog-api-key": settings.gemini_api_key},
        json={"contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"responseMimeType": "application/json", "temperature": 0}},
        timeout=30,
    )
    r.raise_for_status()
    text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    data = json.loads(text)
    interview_at = None
    if data.get("interview_at"):
        try:
            interview_at = datetime.fromisoformat(data["interview_at"])
            if interview_at.tzinfo is None:
                interview_at = None  # a time without a zone could be off by hours; skip it
        except ValueError:
            pass
    kind = data.get("type", "other")
    return Classification(
        is_job_related=bool(data.get("is_job_related")),
        type=kind if kind in {"applied", "interviewing", "offer", "rejected", "other"} else "other",
        company=(data.get("company") or "").strip(),
        role=(data.get("role") or "").strip(),
        confidence=float(data.get("confidence") or 0),
        interview_at=interview_at,
        from_recruiter=bool(data.get("from_recruiter")),
    )


def _classify_rules(sender: str, subject: str, body: str) -> Classification:
    kind, strength = extract_status(subject, body)
    company = extract_company(sender, subject, body)
    role = extract_role(subject, body, company)
    ok = kind != "other" and bool(company)
    confidence = min(0.95, 0.5 + 0.1 * strength) if ok else 0.2
    return Classification(is_job_related=ok, type=kind, company=company, role=role,
                          confidence=confidence, from_recruiter=not is_automated_sender(sender))
