"""verify_claims: the hallucination guard.

Checks a rewritten line against the "facts corpus" (original resume + experience
bank + what the user confirmed in ask_user answers):

  problems (hard, the rewrite is rejected)
    - a number/percent/$ amount that isn't in the corpus  ("cut load time 40%")
    - a skill/tool from the vocabulary that isn't in the corpus  ("Kubernetes")
  warnings (soft, shown to the user next to the change)
    - a capitalized name/acronym not found in the corpus  (could be a new employer, product…)
    - the line grew a lot longer than the original
"""

from __future__ import annotations

import re

from .keywords import VOCAB, aliases_of, canonical, term_in

NUMBER_RX = re.compile(r"(?<![\w.])\$?\d[\d,]*(?:\.\d+)?\s*(?:%|percent|[kKmMbB]\b|x\b|\+)?")
NAME_RX = re.compile(r"\b(?:[A-Z][a-z]+[A-Z]\w*|[A-Z]{2,}[\w+#]*|[A-Z][\w+#.]*)\b")
# Capitalized words that are normal in resume bullets and prove nothing.
GENERIC = {
    "api", "apis", "ui", "ux", "id", "ok", "us", "usa", "it", "qa", "kpi", "kpis", "roi", "crm", "erp",
    "saas", "b2b", "b2c", "mvp", "pr", "prs", "sla", "slas", "i", "a", "an", "the",
}


def _num_key(raw: str) -> str:
    s = raw.lower().replace(",", "").replace("$", "").replace("percent", "%").replace(" ", "")
    s = s.rstrip("+")
    return s.rstrip("%x") or s


def numbers_in(text: str) -> set[str]:
    return {_num_key(m.group(0)) for m in NUMBER_RX.finditer(text)}


def skill_supported(term: str, corpus: str) -> bool:
    return term_in(canonical(term), corpus) or any(term_in(a, corpus) for a in aliases_of(term))


def skills_in(text: str) -> set[str]:
    found = set()
    for term in VOCAB:
        if term_in(term, text) or any(term_in(a, text) for a in aliases_of(term)):
            found.add(term)
    return found


def verify_claims(new_text: str, corpus: str, original_text: str = "") -> dict:
    problems: list[str] = []
    warnings: list[str] = []

    known_numbers = numbers_in(corpus)
    for m in NUMBER_RX.finditer(new_text):
        key = _num_key(m.group(0))
        if key and key not in known_numbers:
            problems.append(f'"{m.group(0).strip()}" is a number that does not appear in the resume, '
                            "experience bank or the user's answers")

    for term in sorted(skills_in(new_text)):
        if not skill_supported(term, corpus):
            problems.append(f'"{term}" is not in the resume, experience bank or the user\'s answers')

    flagged = {p.split('"')[1].lower() for p in problems if '"' in p}
    for sentence in re.split(r"(?<=[.;:!?])\s+", new_text):
        for i, m in enumerate(NAME_RX.finditer(sentence)):
            word = m.group(0).strip(".")
            if i == 0 and m.start() == 0:
                continue  # sentence-initial capital (usually the action verb)
            low = word.lower()
            if low in GENERIC or low in flagged or len(word) < 2:
                continue
            if not re.search(r"(?<![a-z0-9])" + re.escape(low) + r"(?![a-z0-9])", corpus.lower()):
                warnings.append(f'"{word}" isn\'t in the original resume — check it\'s accurate')
                flagged.add(low)

    if original_text:
        before, after = len(original_text.split()), len(new_text.split())
        if before >= 5 and after > before * 1.8:
            warnings.append(f"Much longer than the original ({before} → {after} words)")

    return {"ok": not problems, "problems": problems, "warnings": warnings}
