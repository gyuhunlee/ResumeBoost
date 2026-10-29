"""Decides whether an email is about a job application, and what it says.

Two stages:
1. prefilter()  free keyword/sender check that drops ~95% of an inbox
2. classify()   LLM (Gemini) for the survivors, with a rule-based fallback
                when no API key is set or the call fails
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from email.utils import parseaddr

import httpx

from ..config import settings

log = logging.getLogger(__name__)

# Applicant tracking systems that send confirmation / status emails.
ATS_DOMAINS = (
    "greenhouse.io", "greenhouse-mail.io", "lever.co", "hire.lever.co", "myworkday.com",
    "myworkdayjobs.com", "ashbyhq.com", "icims.com", "smartrecruiters.com", "workable.com",
    "jobvite.com", "bamboohr.com", "taleo.net", "successfactors.com", "breezy.hr",
    "recruitee.com", "jazzhr.com", "applytojob.com", "paylocity.com", "ultipro.com",
    "rippling.com", "dover.com", "governmentjobs.com", "neogov.com",
)

SUBJECT_HINTS = re.compile(
    r"application|applying|applied|your candidacy|interview|next steps|unfortunately|"
    r"thank you for your interest|regarding your|offer letter|job offer|assessment|"
    r"coding challenge|position|role at",
    re.I,
)

# Job boards send lots of "jobs you may like" mail that mentions roles but isn't an application.
NOISE = re.compile(r"jobs? (alert|recommendation)|recommended jobs|new jobs for you|"
                   r"is hiring|apply now|jobs you might|newsletter|webinar", re.I)

SKIP_LABELS = {"CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL", "SPAM", "TRASH", "SENT", "DRAFT"}

# Gmail search used for the first (backfill) sync, so we only list likely emails.
BACKFILL_QUERY = (
    "-category:promotions -category:social "
    "{from:(" + " OR ".join(ATS_DOMAINS) + ") "
    'OR subject:(application OR applying OR applied OR interview OR "next steps" '
    'OR unfortunately OR "thank you for your interest" OR offer OR assessment)}'
)


def sender_domain(sender: str) -> str:
    return parseaddr(sender)[1].rpartition("@")[2].lower()


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


PROMPT = """You read emails for a job-application tracker. Decide if this email is a
message from an employer or recruiting system about an application the recipient
SUBMITTED. Job alerts, newsletters, marketing and recruiter cold outreach are NOT.

Return JSON only:
{{"is_job_related": bool,
  "type": "applied" | "interviewing" | "offer" | "rejected" | "other",
  "company": "hiring company name, not the ATS vendor (e.g. Acme, not Greenhouse)",
  "role": "job title, or empty string if not stated",
  "interview_at": "ISO 8601 datetime with offset if a specific interview time is given, else null",
  "confidence": number 0-1}}

Types: applied = application received/confirmation; interviewing = interview
invitation, scheduling, or assessment/coding challenge; offer = job offer;
rejected = not moving forward; other = job-related but none of these.

Email received: {received}
From: {sender}
Subject: {subject}
Body:
{body}"""


def classify(sender: str, subject: str, body: str, received: datetime) -> Classification:
    if settings.gemini_api_key:
        try:
            return _classify_llm(sender, subject, body, received)
        except Exception as e:  # network error, quota, bad JSON → don't lose the email
            log.warning("LLM classify failed, using rules: %s", e)
    return _classify_rules(sender, subject, body)


def _classify_llm(sender: str, subject: str, body: str, received: datetime) -> Classification:
    prompt = PROMPT.format(received=received.isoformat(), sender=sender,
                           subject=subject, body=body[:1500])
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
    return Classification(
        is_job_related=bool(data.get("is_job_related")),
        type=data.get("type", "other"),
        company=(data.get("company") or "").strip(),
        role=(data.get("role") or "").strip(),
        confidence=float(data.get("confidence") or 0),
        interview_at=interview_at,
    )


# ---- Rule-based fallback --------------------------------------------------------
_RULES = [
    ("rejected", re.compile(r"unfortunately|not (to )?(be )?mov(e|ing) forward|other candidates|"
                            r"decided to pursue|will not be proceeding|position has been filled|"
                            r"regret to inform", re.I)),
    ("offer", re.compile(r"pleased to offer|offer letter|extend (you )?an offer|job offer", re.I)),
    ("interviewing", re.compile(r"interview|schedule (a|some) time|phone screen|"
                                r"coding (challenge|assessment)|next steps|availability", re.I)),
    ("applied", re.compile(r"(received|receipt of) your application|thank you for (applying|your application)|"
                           r"application (was )?(submitted|received)|thanks for applying", re.I)),
]

_COMPANY_PATTERNS = [
    re.compile(r"(?:applying|application|interest) (?:to|at|with) ([A-Z][\w&.\- ]{1,40}?)(?:[!.,]| for | -|$)"),
    re.compile(r"at ([A-Z][\w&.\- ]{1,40}?)(?:[!.,]| -|$)"),
]
# A run of capitalized words right before "position"/"role"/"opening", e.g. "the Data Analyst position".
_ROLE_PATTERN = re.compile(r"(?i:for|the|as) (?:(?i:the|a|an) )?((?:[A-Z][\w/&+#.\-]*,? ){1,6})(?i:position|role|opening)")


def _classify_rules(sender: str, subject: str, body: str) -> Classification:
    text = f"{subject}\n{body[:3000]}"
    kind = next((k for k, rx in _RULES if rx.search(text)), "other")

    company = ""
    for rx in _COMPANY_PATTERNS:
        if m := rx.search(subject) or rx.search(body[:600]):
            company = m.group(1).strip()
            break
    if not company:
        # Use the display name ("Acme Recruiting <no-reply@greenhouse.io>") when it isn't the ATS itself.
        name = parseaddr(sender)[0]
        if m := re.search(r"\bat (.+)$", name):  # "Jane at Globex" → "Globex"
            name = m.group(1)
        name = re.sub(r"\b(recruiting|careers|talent|hiring|team|jobs|hr|no-?reply)\b", "", name, flags=re.I).strip(" -|")
        if name and not any(d.split(".")[0] in name.lower() for d in ATS_DOMAINS):
            company = name

    role_match = _ROLE_PATTERN.search(subject) or _ROLE_PATTERN.search(body[:600])
    role = role_match.group(1).strip(" ,") if role_match else ""

    ok = kind != "other" and bool(company)
    return Classification(is_job_related=ok, type=kind, company=company, role=role,
                          confidence=0.7 if ok else 0.2)
