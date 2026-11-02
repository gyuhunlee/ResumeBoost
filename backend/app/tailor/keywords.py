"""Deterministic keyword matching: keyword_gap() and score_match().

No LLM here on purpose: the score must be reproducible (same input, same
number) so the before/after comparison means something.

Matching levels for each job keyword:
  exact    the keyword itself appears ("PostgreSQL")
  partial  only a synonym or near spelling appears ("Postgres") — an ATS doing
           literal matching may miss it, so the agent should reword to the exact term
  missing  nothing found
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher

from .models import JobAnalysis, ResumeDoc

# canonical (as shown to the user) -> other spellings of the SAME thing.
# Only true equivalents belong here: verify_claims treats an alias in the
# resume as proof of the canonical term, so "containers" must NOT be an alias
# of "Docker" (that would let the agent invent Docker experience).
ALIASES: dict[str, list[str]] = {
    "JavaScript": ["js", "ecmascript", "es6"],
    "TypeScript": [],
    "Node.js": ["node", "nodejs", "node js"],
    "React": ["react.js", "reactjs", "react js"],
    "Next.js": ["nextjs", "next js"],
    "Vue.js": ["vue", "vuejs"],
    "Angular": ["angularjs"],
    "Python": [],
    "Java": [],
    "C++": ["cpp"],
    "C#": ["csharp", "c sharp"],
    "Go": ["golang"],
    "Rust": [],
    "Ruby on Rails": ["rails", "ror"],
    "SQL": [],
    "PostgreSQL": ["postgres", "psql"],
    "MySQL": [],
    "MongoDB": ["mongo"],
    "Redis": [],
    "GraphQL": [],
    "REST APIs": ["rest", "restful", "rest api", "restful apis", "restful api"],
    "FastAPI": [],
    "Django": [],
    "Flask": [],
    "Spring Boot": [],
    "AWS": ["amazon web services"],
    "GCP": ["google cloud", "google cloud platform"],
    "Azure": ["microsoft azure"],
    "Docker": [],
    "Kubernetes": ["k8s"],
    "Terraform": [],
    "CI/CD": ["ci cd", "cicd", "continuous integration", "continuous delivery", "continuous deployment"],
    "GitHub Actions": [],
    "Git": ["github", "gitlab"],
    "Linux": [],
    "Machine learning": ["ml"],
    "Deep learning": [],
    "PyTorch": ["torch"],
    "TensorFlow": [],
    "scikit-learn": ["sklearn", "scikit learn"],
    "Pandas": [],
    "NumPy": [],
    "Data analysis": ["data analytics"],
    "Data visualization": ["data viz"],
    "Tableau": [],
    "Power BI": ["powerbi"],
    "Excel": ["microsoft excel"],
    "LLMs": ["llm", "large language models", "large language model"],
    "Tailwind CSS": ["tailwind"],
    "HTML": ["html5"],
    "CSS": ["css3"],
    "Unit testing": ["unit tests"],
    "Testing": ["test automation"],
    "Agile": ["scrum"],
    "Microservices": ["micro-services", "microservice"],
    "System design": [],
    "Communication": ["communication skills"],
    "Leadership": [],
    "Collaboration": ["collaborated"],
    "Problem solving": ["problem-solving"],
    "Customer service": ["customer support", "client service"],
    "Project management": [],
    "SCADA": [],
    "OSHA": [],
    "Water treatment": ["wastewater treatment"],
    "AutoCAD": [],
    "MATLAB": [],
    "Salesforce": [],
    "Figma": [],
}

# Extra terms the rule-based JD fallback looks for (no aliases needed).
EXTRA_VOCAB = [
    "Kotlin", "Swift", "iOS", "Android", "R", "Scala", "Spark", "Hadoop", "Kafka", "Airflow",
    "Snowflake", "BigQuery", "dbt", "ETL", "Elasticsearch", "Nginx", "Jenkins", "Ansible",
    "Vercel", "Supabase", "Firebase", "OAuth", "Security", "Accessibility", "Jira",
    "Statistics", "A/B testing", "NLP", "Computer vision", "Prompt engineering",
]

_ALIAS_TO_CANON = {a.lower(): c for c, al in ALIASES.items() for a in al}
_CANON_LOWER = {c.lower(): c for c in [*ALIASES, *EXTRA_VOCAB]}
VOCAB: list[str] = [*ALIASES, *EXTRA_VOCAB]


def canonical(term: str) -> str:
    t = term.strip()
    low = t.lower()
    return _CANON_LOWER.get(low) or _ALIAS_TO_CANON.get(low) or t


def _pattern(term: str) -> re.Pattern[str]:
    """Whole-term match, tolerant of plural 's' and of '.'/'-'/' ' variants."""
    t = re.escape(term.lower()).replace(r"\-", "\x00").replace(r"\ ", "\x01")
    t = t.replace("\x00", r"[\s\-]?").replace("\x01", r"[\s\-]+")
    if t.endswith("s") and len(term) > 3:
        t = t[:-1] + "s?"
    else:
        t += "(?:e?s)?"
    return re.compile(r"(?<![a-z0-9+#])" + t + r"(?![a-z0-9+#])", re.I)


# Skills that are also everyday words ("go", "rust") only count when capitalized.
CASE_SENSITIVE = {"Go", "R", "Rust", "Swift", "Spark", "Excel", "Salesforce"}


def term_in(term: str, text: str) -> bool:
    if term in CASE_SENSITIVE:
        return bool(re.search(r"(?<![A-Za-z0-9+#])" + re.escape(term) + r"(?![A-Za-z0-9+#])", text))
    return bool(_pattern(term).search(text))


def aliases_of(term: str) -> list[str]:
    return ALIASES.get(canonical(term), [])


@dataclass
class KeywordHit:
    keyword: str
    level: str               # exact | partial | missing
    found_as: str = ""       # the alias/near spelling found, for partial
    bullet_ids: list[str] = field(default_factory=list)


def _fuzzy_found(term: str, text: str) -> str:
    """Near-spelling for multi-letter terms ("Javascript ES6" vs "JavaScript")."""
    if len(term) < 5:
        return ""
    words = re.findall(r"[A-Za-z][\w.+#/-]*", text)
    n = len(term.split())
    for i in range(len(words)):
        cand = " ".join(words[i:i + n])
        if SequenceMatcher(None, cand.lower(), term.lower()).ratio() >= 0.88:
            return cand
    return ""


def match_keyword(term: str, doc: ResumeDoc, text: str | None = None) -> KeywordHit:
    text = text if text is not None else doc.text()
    ids_exact = [b.id for _, _, b in doc.bullets() if term_in(term, b.text)]
    if term_in(term, text):
        return KeywordHit(term, "exact", bullet_ids=ids_exact)
    for alias in aliases_of(term):
        if term_in(alias, text):
            ids = [b.id for _, _, b in doc.bullets() if term_in(alias, b.text)]
            return KeywordHit(term, "partial", found_as=alias, bullet_ids=ids)
    near = _fuzzy_found(term, text)
    if near:
        return KeywordHit(term, "partial", found_as=near)
    return KeywordHit(term, "missing")


def _dedupe(terms: list[str]) -> list[str]:
    seen, out = set(), []
    for t in terms:
        k = canonical(t).lower()
        if t.strip() and k not in seen:
            seen.add(k)
            out.append(t.strip())
    return out


def keyword_gap(doc: ResumeDoc, job: JobAnalysis) -> dict:
    text = doc.text()
    req = [match_keyword(t, doc, text) for t in _dedupe(job.required)]
    req_keys = {canonical(h.keyword).lower() for h in req}
    pref = [match_keyword(t, doc, text) for t in _dedupe(job.preferred)
            if canonical(t).lower() not in req_keys]

    def group(hits: list[KeywordHit], level: str) -> list[dict]:
        return [{k: v for k, v in asdict(h).items() if v or k == "keyword"} for h in hits if h.level == level]

    return {
        "required": {lvl: group(req, lvl) for lvl in ("exact", "partial", "missing")},
        "preferred": {lvl: group(pref, lvl) for lvl in ("exact", "partial", "missing")},
    }


# ---- Score -----------------------------------------------------------------------
REQUIRED_WEIGHT = 3
PREFERRED_WEIGHT = 1
PARTIAL_CREDIT = 0.6
_LEVEL_CREDIT = {"exact": 1.0, "partial": PARTIAL_CREDIT, "missing": 0.0}
_TITLE_STOP = {"i", "ii", "iii", "iv", "senior", "junior", "sr", "jr", "the", "a", "an", "of", "and", "-", "&", "lead"}


def _title_similarity(doc: ResumeDoc, title: str) -> float:
    """Share of the job title's words that appear in the resume's headings/summary."""
    words = [w for w in re.findall(r"[a-z0-9+#]+", title.lower()) if w not in _TITLE_STOP]
    if not words:
        return 1.0
    head = " ".join([e.heading for s in doc.sections for e in s.entries] +
                    [b.text for s in doc.sections if s.kind == "summary" for e in s.entries for b in e.bullets])
    return sum(term_in(w, head) for w in words) / len(words)


def score_match(doc: ResumeDoc, job: JobAnalysis) -> dict:
    """0–100. 85% weighted keyword coverage + 15% job-title alignment."""
    gap = keyword_gap(doc, job)
    got = total = 0.0
    for bucket, weight in (("required", REQUIRED_WEIGHT), ("preferred", PREFERRED_WEIGHT)):
        for level, hits in gap[bucket].items():
            total += weight * len(hits)
            got += weight * _LEVEL_CREDIT[level] * len(hits)
    coverage = got / total if total else 1.0
    title = _title_similarity(doc, job.title) if job.title else 1.0
    score = round(100 * (0.85 * coverage + 0.15 * title))
    flat = lambda lvl: [h["keyword"] for b in ("required", "preferred") for h in gap[b][lvl]]  # noqa: E731
    return {
        "score": max(0, min(100, score)),
        "keyword_coverage": round(coverage, 3),
        "title_alignment": round(title, 3),
        "matched": flat("exact"),
        "partial": flat("partial"),
        "missing": flat("missing"),
    }
