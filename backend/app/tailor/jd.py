"""analyze_job_description: posting text -> JobAnalysis (required vs preferred terms)."""

from __future__ import annotations

import logging
import re

from pydantic import ValidationError

from .keywords import VOCAB, canonical, term_in
from .llm import LLM, LLMError
from .models import JobAnalysis

log = logging.getLogger(__name__)

PROMPT = """Extract what an applicant tracking system would screen for in this job posting.
Return JSON only:
{{"title": "job title",
  "seniority": "intern" | "entry" | "mid" | "senior" | "lead" | "",
  "required": ["hard requirements: skills, tools, languages, certifications, degrees"],
  "preferred": ["nice-to-haves / bonus / preferred qualifications"],
  "responsibilities": ["main duties, max 6, short"]}}

Rules: keywords must be short (1-4 words) and use the posting's exact spelling
("PostgreSQL", not "Postgres databases"). Include important soft skills only if the
posting stresses them. Max 15 required and 10 preferred. No duplicates.

Job title given by the user: {title}
Posting:
{jd}"""


def analyze_rules(jd: str, title: str = "") -> JobAnalysis:
    """Vocabulary scan. Terms first seen after a 'Preferred/Nice to have' heading are preferred."""
    m = re.search(r"^\s*(preferred|nice[- ]to[- ]have|bonus|desired)[^\n]*$", jd, re.I | re.M)
    split = m.start() if m else len(jd)
    req, pref = [], []
    for term in VOCAB:
        if term_in(term, jd[:split]):
            req.append(term)
        elif term_in(term, jd[split:]):
            pref.append(term)
    return JobAnalysis(title=title, required=req, preferred=pref)


def analyze_job_description(jd: str, title: str = "", llm: LLM | None = None) -> JobAnalysis:
    if llm is None:
        return analyze_rules(jd, title)
    try:
        data = llm.generate_json(PROMPT.format(title=title or "(not given)", jd=jd[:12000]))
        job = JobAnalysis.model_validate(data)
    except (LLMError, ValidationError, TypeError) as e:
        log.warning("LLM JD analysis failed, using rules: %s", e)
        return analyze_rules(jd, title)

    def clean(terms: list[str], limit: int) -> list[str]:
        out, seen = [], set()
        for t in terms:
            t = re.sub(r"\s+", " ", str(t)).strip(" .,;")
            k = canonical(t).lower()
            if t and len(t) <= 40 and k not in seen:
                seen.add(k)
                out.append(t)
        return out[:limit]

    job.title = job.title or title
    job.required = clean(job.required, 15)
    req_keys = {canonical(t).lower() for t in job.required}
    job.preferred = [t for t in clean(job.preferred, 10) if canonical(t).lower() not in req_keys]
    job.responsibilities = job.responsibilities[:6]
    if not job.required and not job.preferred:
        return analyze_rules(jd, title)
    return job
