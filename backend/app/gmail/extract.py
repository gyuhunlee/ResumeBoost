"""Pulls company, role and status out of an application email, precisely.

Why this exists: the sender is often NOT the company. A recruiter writes as
"Jane Kim", an ATS writes as "Greenhouse" or "Workday", and a job board writes
as "LinkedIn". So the company is never taken from one place. Instead:

1. Collect candidates from several independent signals, each with a weight:
     - phrases in the subject/body  ("thank you for applying to Acme")
     - the careers link in the email (boards.greenhouse.io/acme, acme.wd5.myworkdayjobs.com)
     - the sender's own domain       (jane@acme.com → Acme), unless it's an ATS/job board/free mail
     - the sender's display name     ("Acme Recruiting"), unless it's a person or a vendor
     - a sign-off                    ("The Acme Talent Team")
2. Reject anything that is a person's name, an ATS/job-board vendor, or a
   generic word ("Our Team", "Hiring Team").
3. Merge candidates that refer to the same company and pick the best-supported
   one, using the spelling that actually appears in the email.

The same validators check the LLM's answer (classify.py), so a model that
returns the sender's name is caught and corrected.

Stdlib only, so it is fast and easy to test.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from email.utils import parseaddr

# ---- Vendors: they send the email but are never the hiring company ---------------
ATS_DOMAINS = (
    "greenhouse.io", "greenhouse-mail.io", "lever.co", "hire.lever.co", "myworkday.com",
    "myworkdayjobs.com", "ashbyhq.com", "icims.com", "smartrecruiters.com", "workable.com",
    "jobvite.com", "bamboohr.com", "taleo.net", "successfactors.com", "breezy.hr",
    "recruitee.com", "jazzhr.com", "applytojob.com", "paylocity.com", "ultipro.com",
    "rippling.com", "dover.com", "governmentjobs.com", "neogov.com", "schooljobs.com",
    "oraclecloud.com", "adp.com", "paycomonline.net", "teamtailor.com", "pinpointhq.com",
    "eightfold.ai", "phenompeople.com", "avature.net", "csod.com", "hirebridge.com",
)
JOB_BOARD_DOMAINS = (
    "linkedin.com", "indeed.com", "indeedemail.com", "ziprecruiter.com", "glassdoor.com",
    "handshake.com", "joinhandshake.com", "wellfound.com", "angel.co", "dice.com",
    "monster.com", "simplyhired.com", "builtin.com", "otta.com", "hired.com",
)
FREE_MAIL = ("gmail.com", "googlemail.com", "yahoo.com", "outlook.com", "hotmail.com",
             "live.com", "icloud.com", "me.com", "aol.com", "proton.me", "protonmail.com")

VENDOR_NAMES = {
    "greenhouse", "lever", "workday", "ashby", "icims", "smartrecruiters", "workable",
    "jobvite", "bamboohr", "bamboo hr", "taleo", "successfactors", "sap successfactors",
    "breezy", "breezy hr", "recruitee", "jazzhr", "jazz hr", "paylocity", "ultipro", "ukg",
    "rippling", "dover", "governmentjobs", "government jobs", "neogov", "linkedin",
    "linkedin jobs", "indeed", "indeed apply", "ziprecruiter", "glassdoor", "handshake",
    "wellfound", "dice", "monster", "adp", "oracle", "oracle cloud", "teamtailor", "pinpoint",
    "eightfold", "phenom", "avature", "cornerstone", "applytojob", "schooljobs",
}

# Words that look like a name in a sentence but aren't a company.
GENERIC = {
    "us", "we", "our", "our team", "the team", "team", "hiring team", "recruiting team",
    "talent team", "talent acquisition", "talent acquisition team", "recruiting", "recruitment",
    "human resources", "hr", "careers", "career", "jobs", "the company", "company", "this position",
    "this role", "the position", "the role", "your application", "application", "candidate",
    "no reply", "noreply", "do not reply", "notifications", "the hiring manager", "hiring manager",
    "people team", "people operations", "talent", "you", "your", "this", "the", "a", "an",
    "dear", "hello", "hi", "thank you", "thanks", "unfortunately", "congratulations",
}

_ROLE_WORDS = (
    r"engineer|developer|programmer|analyst|scientist|designer|manager|director|lead|"
    r"architect|administrator|admin|specialist|coordinator|assistant|associate|consultant|"
    r"intern|internship|co-?op|technician|operator|trainee|apprentice|in-training|"
    r"representative|rep|officer|accountant|clerk|inspector|mechanic|electrician|planner|"
    r"strategist|writer|editor|researcher|recruiter|advisor|agent|supervisor|attendant|"
    r"nurse|teacher|tutor|instructor|counselor|chemist|biologist|worker|aide|"
    r"sde|swe|devops|sre|qa|tester|fellow|generalist|partner|producer|marketer|buyer"
)
ROLE_WORD = re.compile(rf"\b({_ROLE_WORDS})s?\b", re.I)


# ---- Small helpers -----------------------------------------------------------------
def sender_parts(sender: str) -> tuple[str, str, str]:
    """('Jane Kim', 'jane.kim', 'acme.com')"""
    name, addr = parseaddr(sender)
    local, _, domain = addr.lower().partition("@")
    return name.strip().strip('"'), local, domain


def _on(domain: str, roots: tuple[str, ...]) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in roots)


def is_vendor_domain(domain: str) -> bool:
    return _on(domain, ATS_DOMAINS) or _on(domain, JOB_BOARD_DOMAINS)


def key(name: str) -> str:
    """Comparison key: lowercase, no legal suffix or punctuation."""
    s = re.sub(r"\b(inc|incorporated|llc|ltd|limited|corp|corporation|co|plc|gmbh|the)\b\.?", " ",
               name.lower())
    return re.sub(r"[^a-z0-9]+", "", s)


def same_company(a: str, b: str) -> bool:
    ka, kb = key(a), key(b)
    if not ka or not kb:
        return False
    if ka == kb or (min(len(ka), len(kb)) >= 4 and (ka.startswith(kb) or kb.startswith(ka))):
        return True
    return SequenceMatcher(None, ka, kb).ratio() >= 0.88


_PERSON_LOCAL = re.compile(r"^[a-z]+[._-][a-z]+\d*$|^[a-z]\.?[a-z]{2,}\d*$")
_COMPANYISH = re.compile(
    r"\b(inc|llc|ltd|corp|co|company|group|labs?|technologies|tech|systems|solutions|health|"
    r"bank|capital|partners|studios?|games|software|city|county|state|district|university|"
    r"college|school|hospital|department|agency|authority|foundation|institute|services|"
    r"energy|water|power|motors|airlines|media|ai)\b", re.I)


_LEGAL = re.compile(r"\b(inc|llc|ltd|corp|corporation|company|co|plc|gmbh|group|partners)\b\.?", re.I)
_NOT_A_NAME = re.compile(r"\b(application|applications|received|interview|invitation|thank|thanks|your|update|"
                         r"status|next steps|confirmation|regarding|re|fwd|offer|congratulations|reminder)\b", re.I)


def looks_like_person(name: str, sender: str = "") -> bool:
    """'Jane Kim' or 'jane.kim@…' → True. 'Acme Health' → False."""
    name = name.strip()
    if not name or _COMPANYISH.search(name):
        return False
    s_name, local, _ = sender_parts(sender) if sender else ("", "", "")
    words = re.findall(r"[A-Za-z][A-Za-z'\-]+", name)
    # The display name of a sender whose mailbox looks like firstname.lastname.
    if s_name and key(name) == key(s_name) and _PERSON_LOCAL.match(local or ""):
        first = local.split(".")[0].split("_")[0].split("-")[0]
        if any(w.lower().startswith(first[:3]) for w in words if len(first) >= 3):
            return True
    # "Jane Kim", "Jane M. Kim": 2-3 capitalized words, none a company-ish word.
    return 2 <= len(words) <= 3 and all(w[0].isupper() and not w.isupper() for w in words) \
        and bool(s_name) and key(name) == key(s_name)


def is_bad_company(name: str, sender: str = "") -> bool:
    k = name.strip().lower().strip(" .,-|:")
    if len(k) < 2 or k in GENERIC or k in VENDOR_NAMES or key(name) in {key(v) for v in VENDOR_NAMES}:
        return True
    if ROLE_WORD.search(k) and not _LEGAL.search(k):  # "Software Engineer" isn't a company
        return True
    if _NOT_A_NAME.search(k):  # "Application Received", "Interview Invitation"
        return True
    if re.fullmatch(r"[\d\W_]+", k):
        return True
    return looks_like_person(name, sender)


def clean_body(body: str) -> str:
    """Drop quoted replies and legal/unsubscribe footers so they can't mislead the parser."""
    body = re.split(r"\bOn (?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[^\n]{0,80}wrote:|-{2,} ?Original Message ?-{2,}|"
                    r"\n>.*", body, maxsplit=1)[0]
    body = re.split(r"(?i)\b(unsubscribe|privacy policy|this email was sent (?:to|by)|"
                    r"you are receiving this|do not reply to this (?:e-?mail|message))\b", body, maxsplit=1)[0]
    return body.strip()


# ---- Company -----------------------------------------------------------------------
# A company name: capitalized words (allowing &, ., -, ', digits), up to 6 words.
_TOK = r"[A-Z0-9][\w&'’\-]*(?:\.[A-Za-z0-9][\w&'’\-]*)*"
_NAME = rf"({_TOK}(?:[ ](?:of|and|the|de|&|{_TOK})){{0,5}})"

COMPANY_PATTERNS: list[tuple[re.Pattern, float]] = [
    (re.compile(rf"(?i:applying|applied|application|apply)\s+(?i:to|at|with)\s+(?:(?i:the)\s+)?{_NAME}"), 3.0),
    (re.compile(rf"(?i:interest|interested)\s+in\s+(?:joining\s+|working\s+(?:at|for|with)\s+)?(?:the\s+)?{_NAME}"), 2.5),
    (re.compile(rf"(?i:position|role|opening|opportunity|job|career|careers)\s+(?i:at|with)\s+(?:(?i:the)\s+)?{_NAME}"), 3.0),
    (re.compile(rf"(?i:join|joining|joined)\s+(?:the\s+)?{_NAME}\s+(?i:team|family)"), 2.5),
    (re.compile(rf"(?i:application\s+was\s+sent\s+to)\s+{_NAME}"), 3.0),           # LinkedIn
    (re.compile(rf"(?i:your|the)\s+(?i:application)\s+(?i:to|with)\s+(?:the\s+)?{_NAME}"), 2.0),
    (re.compile(rf"(?i:on behalf of|here at|everyone at|team at|hiring at)\s+(?:the\s+)?{_NAME}"), 2.5),
    (re.compile(rf"(?i:offer|employment)\s+(?i:from|with)\s+(?:the\s+)?{_NAME}"), 2.5),
    (re.compile(rf"\b(?:at|with)\s+(?:the\s+)?{_NAME}(?=\s*(?:[!.,;:]|$|\s-\s|\son\b|\sis\b))"), 1.0),
]
# Sign-offs: "The Acme Recruiting Team", "Acme Talent Acquisition"
SIGNOFF = re.compile(
    rf"(?:^|\n|\.\s|,\s)(?:The\s+)?{_NAME}\s+(?:Recruiting|Recruitment|Talent(?: Acquisition)?|Hiring|"
    rf"People|HR|Human Resources|Careers)(?:\s+Team)?\b")
# Subject formats: "Application received - Data Analyst at Acme", "Acme | Data Analyst"
SUBJECT_AT = re.compile(rf"\bat\s+{_NAME}\s*$")
SUBJECT_PREFIX = re.compile(rf"^\s*{_NAME}\s*[:|]\s")  # "Sacramento County: Invitation to …"

# Careers links → company slug.
URL_SLUGS: list[re.Pattern] = [re.compile(p, re.I) for p in (
    r"(?:boards|job-boards)\.(?:eu\.)?greenhouse\.io/([a-z0-9][\w-]+)",
    r"jobs\.(?:eu\.)?lever\.co/([a-z0-9][\w-]+)",
    r"jobs\.ashbyhq\.com/([a-z0-9][\w.-]+)",
    r"apply\.workable\.com/([a-z0-9][\w-]+)",
    r"jobs\.smartrecruiters\.com/([a-z0-9][\w-]+)",
    r"jobs\.jobvite\.com/([a-z0-9][\w-]+)",
    r"governmentjobs\.com/careers/([a-z0-9][\w-]+)",
    r"//([a-z0-9][\w-]+)\.wd\d+\.myworkday(?:jobs)?\.com",
    r"//([a-z0-9][\w-]+)\.(?:bamboohr\.com|breezy\.hr|recruitee\.com|applytojob\.com|teamtailor\.com|pinpointhq\.com)",
    r"//careers-([a-z0-9][\w-]+)\.icims\.com",
)]
_SLUG_JUNK = {"www", "jobs", "careers", "apply", "boards", "job-boards", "embed", "us", "eu", "app", "en", "en-us"}


@dataclass
class Candidate:
    name: str
    score: float
    sources: list[str] = field(default_factory=list)


def _trim_name(name: str) -> str:
    name = re.sub(r"[\s,.:;!|\-–—]+$", "", name.strip())
    # Cut trailing words that belong to the sentence, not the name.
    name = re.sub(r"\s+(?:for|and|to|as|in|on|we|our|is|has|have|team|recruiting|careers|"
                  r"talent|hiring|position|role|via)\b.*$", "", name, flags=re.I)
    name = re.sub(r"^(?:the)\s+", "", name, flags=re.I)
    return name.strip(" .,'’-")


def _pretty_slug(slug: str) -> str:
    slug = re.sub(r"(careers?|jobs|hiring|inc|llc|corp)$", "", slug.lower()).strip("-_.")
    return " ".join(p.capitalize() for p in re.split(r"[-_.]+", slug) if p)


def _spelled_in(text: str, rough: str) -> str | None:
    """The way a slug/domain like 'northwindtraders' is actually written: 'Northwind Traders'."""
    target = key(rough)
    if len(target) < 3:
        return None
    for m in re.finditer(r"[A-Z][\w&'’.\-]*(?:\s+[A-Z&][\w&'’.\-]*){0,4}", text):
        words = m.group(0).split()
        for i in range(len(words)):
            for j in range(i + 1, len(words) + 1):
                phrase = " ".join(words[i:j]).strip(".,")
                if key(phrase) == target:
                    return phrase
    return None


def company_candidates(sender: str, subject: str, body: str) -> list[Candidate]:
    s_name, local, domain = sender_parts(sender)
    text = f"{subject}\n{body[:4000]}"
    found: list[tuple[str, float, str]] = []

    for rx, weight in COMPANY_PATTERNS:
        for m in rx.finditer(text):
            found.append((_trim_name(m.group(1)), weight, "phrase"))
    for m in SIGNOFF.finditer(text):
        found.append((_trim_name(m.group(1)), 2.5, "signoff"))
    if m := SUBJECT_AT.search(subject):
        found.append((_trim_name(m.group(1)), 2.0, "subject"))
    if m := SUBJECT_PREFIX.search(subject):
        found.append((_trim_name(m.group(1)), 2.0, "subject"))

    for rx in URL_SLUGS:
        for m in rx.finditer(body):
            slug = m.group(1)
            if slug.lower() not in _SLUG_JUNK:
                found.append((_spelled_in(text, slug) or _pretty_slug(slug), 3.0, "link"))

    # Workday etc. sometimes send from acme@myworkday.com: the mailbox is the company.
    if _on(domain, ATS_DOMAINS) and local and not re.match(r"^(no-?reply|notifications?|donotreply|support|info)", local):
        found.append((_spelled_in(text, local) or _pretty_slug(local), 1.5, "ats-mailbox"))

    # The sender's own domain, when it's the employer's mail server.
    if domain and not is_vendor_domain(domain) and not _on(domain, FREE_MAIL):
        parts = domain.split(".")
        root = parts[-3] if len(parts) >= 3 and parts[-2] in {"co", "com", "org", "gov", "ac"} else parts[-2] if len(parts) >= 2 else parts[0]
        if parts[-1] == "gov" or parts[-2:] == ["ca", "gov"] or "cityof" in root:
            root = re.sub(r"^(cityof|countyof|ci|co)", "", root)
            spelled = _spelled_in(text, f"city of {root}") or _spelled_in(text, root)
            found.append((spelled or f"City of {root.capitalize()}", 2.0, "domain"))
        else:
            found.append((_spelled_in(text, root) or _pretty_slug(root), 2.0, "domain"))

    # The display name, after removing "Recruiting", "Careers", "via Greenhouse", "Jane at".
    if s_name:
        name = re.sub(r"^.*?\b(?:at|@|from)\s+", "", s_name, flags=re.I) if re.search(r"\b(at|@|from)\s", s_name, re.I) else s_name
        name = re.sub(r"\s*(?:via|through)\s+.*$", "", name, flags=re.I)
        name = re.sub(r"\b(recruiting|recruitment|careers?|talent(?: acquisition)?|hiring|team|jobs|hr|"
                      r"human resources|people|no-?reply|notifications?)\b", "", name, flags=re.I)
        name = name.strip(" -|,:")
        if name and not looks_like_person(s_name, sender):
            found.append((name, 1.5, "display-name"))

    merged: list[Candidate] = []
    for name, weight, src in found:
        if not name or is_bad_company(name, sender) or len(name) > 60:
            continue
        for c in merged:
            if same_company(c.name, name):
                c.score += weight
                c.sources.append(src)
                # Prefer the spelling seen in the text, then the longer one ("Acme Health" over "Acme").
                if src in {"phrase", "signoff", "subject"} and c.sources[0] not in {"phrase", "signoff", "subject"}:
                    c.name = name
                elif src in {"phrase", "signoff", "subject"} and len(name) > len(c.name) and key(name).startswith(key(c.name)):
                    c.name = name
                break
        else:
            merged.append(Candidate(name, weight, [src]))
    return sorted(merged, key=lambda c: c.score, reverse=True)


def extract_company(sender: str, subject: str, body: str) -> str:
    cands = company_candidates(sender, subject, body)
    return cands[0].name if cands and cands[0].score >= 1.5 else ""


def company_supported(name: str, sender: str, subject: str, body: str) -> bool:
    """Is a proposed company (e.g. from the LLM) backed by the email itself?"""
    if not name or is_bad_company(name, sender):
        return False
    text = f"{subject}\n{body[:4000]}"
    if key(name) and key(name) in key(text):
        return True
    return any(same_company(c.name, name) for c in company_candidates(sender, subject, body))


# ---- Role --------------------------------------------------------------------------
# Titles stay on one line, so "Backend Engineer\nRequisition ID" stops at the line break.
_TITLE = r"([A-Z][\w/&+#.,()'’\-]*(?:[ \t]+(?:of|and|&|for|in|(?:I{1,3}|IV|V)\b|-|–|[A-Z0-9(][\w/&+#.,()'’\-]*)){0,9})"
ROLE_PATTERNS: list[re.Pattern] = [
    re.compile(rf"(?:^|\n|[.!]\s+)(?i:job\s+title|position(?:\s+title)?|role|title)\s*[:\-–]\s*{_TITLE}"),
    re.compile(rf"(?i:for|the|as|our)\s+(?:(?i:the|a|an)\s+)?{_TITLE}\s+(?i:position|role|opening|job|opportunity|vacancy|internship)\b"),
    re.compile(rf"(?i:position|role)\s+of\s+{_TITLE}"),
    re.compile(rf"(?i:examination|exam|interview|assessment|test)\s+for\s+(?:(?i:the|a|an)\s+)?{_TITLE}"),
    re.compile(rf"(?i:applying|applied|application|candidacy|interest)\s+(?i:to|for|in)\s+(?:(?i:the|a|an)\s+)?{_TITLE}(?=\s+(?:at|with|position|role|and)\b|\s*[(\-–—.,]|\s*$)"),
    re.compile(rf"(?:^|[:\-–—|]\s*){_TITLE}\s+(?:at|with|@)\s+[A-Z]"),       # subject: "Data Analyst at Acme"
    re.compile(rf"(?i:application\s+(?:received|submitted|confirmation)|offer|interview(?:\s+invitation)?)\s*[:\-–—|]\s*{_TITLE}"),
]
_ROLE_TAIL = re.compile(r"\s*(?:\((?:req|job|id|#|remote|hybrid|on-?site|full[- ]time|part[- ]time|contract|temporary)[^)]*\)|"
                        r"\s(?:req(?:uisition)?|job)\s*(?:id|#|no\.?|number)\b.*$|"
                        r"\s(?:location|department|dept|date|salary|pay|closing|posted|reference)\b.*$|\b(?:req(?:uisition)?|job)\s*(?:id|#|no\.?)\s*[:#]?\s*[\w-]+|"
                        r"#\s*\w*\d\w*|\s[-–—|]\s.*$|,\s*(?:remote|hybrid|on-?site).*$|\s+(?:at|with)\s+[A-Z].*$)",
                        re.I)


def _clean_role(raw: str) -> str:
    role = raw.strip(" .,:;\"'“”")
    for _ in range(3):
        role = _ROLE_TAIL.sub("", role).strip(" .,:;-–—")
    role = re.sub(r"^(?:the|a|an|our|your)\s+", "", role, flags=re.I)
    role = re.sub(r"\s+(?:position|role|opening|job)$", "", role, flags=re.I)
    return re.sub(r"\s+", " ", role).strip()


def extract_role(subject: str, body: str, company: str = "") -> str:
    text = f"{subject}\n{body[:3000]}"
    for rx in ROLE_PATTERNS:  # most specific pattern first; its first valid hit wins
        for m in rx.finditer(text):
            role = _clean_role(m.group(1))
            if role_ok(role, company):
                return role
    return ""


def role_ok(role: str, company: str = "") -> bool:
    if not role or len(role) > 80 or len(role.split()) > 10:
        return False
    if company and same_company(role, company):
        return False
    if re.search(r"\b(your|you|we|our|us|thank|application|interest|unfortunately)\b", role, re.I):
        return False
    return bool(ROLE_WORD.search(role))


# ---- Status ------------------------------------------------------------------------
# Conditional mentions of an interview are part of confirmations, not invitations:
# "if your qualifications match, we will contact you to schedule an interview".
CONDITIONAL = re.compile(
    r"(?:if|should|once|in the event)\b[^.]{0,120}\b(interview|next steps|contact you|reach out)|"
    r"(?:may|might|will)\s+(?:be\s+)?(?:contact(?:ed)?|reach out)[^.]{0,60}(?:interview|next steps)|"
    r"(?:selected|chosen|shortlisted)\s+(?:candidates|applicants)[^.]{0,80}(?:interview|contacted)",
    re.I)

STATUS_RULES: list[tuple[str, float, re.Pattern]] = [
    ("offer", 4, re.compile(r"pleased to (?:offer|extend)|offer (?:letter|of employment)|extend (?:you )?an offer|"
                            r"(?:job|formal|verbal|conditional) offer|congratulations[^.]{0,60}\b(?:offer|hired|selected for the position)", re.I)),
    ("rejected", 4, re.compile(r"unfortunately|not (?:to )?(?:be )?mov(?:e|ing) forward|other candidates|"
                               r"decided to (?:pursue|proceed|move forward) with|will not be (?:proceeding|moving|advancing)|"
                               r"position has been (?:filled|closed|cancelled)|regret to inform|not been selected|"
                               r"were not selected|no longer (?:under consideration|being considered)|"
                               r"not (?:a|the right) (?:match|fit)|decided not to|unable to offer|"
                               r"did not (?:meet|pass)|not eligible|disqualified", re.I)),
    ("interviewing", 3, re.compile(r"(?:invite|inviting|invitation)\s+(?:you\s+)?(?:to|for)\s+(?:an?\s+|a\s+)?(?:\w+\s+){0,2}"
                                   r"(?:interview|conversation|chat|call|screen|exam|examination|assessment)|"
                                   r"(?:schedule|book|set up|arrange)\s+(?:an?|your|the|some)\s+(?:\w+\s+){0,2}(?:interview|call|time|screen|chat)|"
                                   r"(?:like|love|want)\s+to\s+(?:schedule|set up|invite|speak|talk|chat|move you forward)|"
                                   r"(?:please|kindly)\s+(?:select|choose|pick|book|share|send|provide|let us know)[^.]{0,40}"
                                   r"(?:time|slot|availability|available)|your availability|calendly\.com|goodtime\.io|"
                                   r"(?:are you|would you be)\s+(?:available|free)|when (?:are you|would you be) (?:free|available)|"
                                   r"what (?:times?|days?) (?:work|suit)|(?:quick|brief|short|intro(?:ductory)?)\s+(?:call|chat)|"
                                   r"phone screen|(?:technical|onsite|on-site|virtual|video|panel|final)\s+interview|"
                                   r"interview (?:is )?(?:scheduled|confirmed)|confirm(?:ing)? your interview|"
                                   r"(?:coding|technical|online)\s+(?:challenge|assessment|test)|take-home|hackerrank|codesignal|"
                                   r"(?:written|oral|performance)\s+(?:exam|examination|test)|move (?:you )?(?:forward|to the next)", re.I)),
    ("applied", 2, re.compile(r"(?:received|receipt of|reviewing)\s+your\s+application|thank you for (?:applying|your application|submitting)|"
                              r"thanks for applying|application (?:has been |was )?(?:submitted|received|sent)|"
                              r"we(?:'ve| have) received|successfully (?:applied|submitted)|application confirmation|"
                              r"your application (?:for|to)\b", re.I)),
]


def extract_status(subject: str, body: str) -> tuple[str, float]:
    """(status, strength). Conditional interview talk is removed before scoring."""
    text = f"{subject}\n{body[:3000]}"
    unconditional = CONDITIONAL.sub(" ", text)
    scores: dict[str, float] = {}
    for status, weight, rx in STATUS_RULES:
        hits = len(rx.findall(unconditional if status == "interviewing" else text))
        if hits:
            scores[status] = weight + min(hits - 1, 2) * 0.5
    if not scores:
        return "other", 0.0
    # "Unfortunately we can't make Tuesday; can you do Thursday?" is still an interview thread.
    if "rejected" in scores and "interviewing" in scores and not re.search(
            r"not (?:to )?(?:be )?mov|other candidates|regret|not been selected|no longer", text, re.I):
        scores.pop("rejected")
    status = max(scores, key=lambda s: scores[s])
    return status, scores[status]


def strong_status(subject: str, body: str) -> str | None:
    """A status the text states so plainly it should override a model's guess."""
    status, strength = extract_status(subject, body)
    return status if status in {"offer", "rejected"} and strength >= 4 else None
