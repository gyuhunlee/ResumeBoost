"""check_format: deterministic resume hygiene checks (length, bullets, sections)."""

from __future__ import annotations

import re
from collections import Counter

from .models import ResumeDoc

ONE_PAGE_WORDS = 650        # rough limit for a one-page resume at 10.5pt
MAX_BULLET_WORDS = 32
MIN_BULLET_WORDS = 5
WEAK_STARTS = re.compile(
    r"^(responsible for|worked on|helped|assisted( with)?|duties included|tasked with|in charge of|"
    r"participated in|was involved)\b", re.I)
PRONOUNS = re.compile(r"\b(I|me|my|we|our)\b")
EMAIL_RX = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def check_format(doc: ResumeDoc, max_words: int = ONE_PAGE_WORDS) -> list[dict]:
    issues: list[dict] = []

    def add(severity: str, message: str, target: str | None = None) -> None:
        issues.append({"severity": severity, "message": message, "target_id": target})

    words = doc.word_count()
    if words > max_words:
        add("warning", f"About {words} words — likely more than one page (aim for under {max_words}). "
                       "Remove the least relevant bullets or projects.")

    kinds = {s.kind for s in doc.sections}
    for kind, label in (("experience", "Experience"), ("education", "Education"), ("skills", "Skills")):
        if kind not in kinds and not (kind == "experience" and "projects" in kinds):
            add("warning", f"No {label} section found. ATS parsers look for standard section names.")
    if not any(EMAIL_RX.search(c) for c in doc.contact):
        add("info", "No email address found in the header.")

    starts: Counter[str] = Counter()
    for s, _, b in doc.bullets():
        if s.kind in ("skills", "summary", "education"):
            continue
        n = len(b.text.split())
        if n > MAX_BULLET_WORDS:
            add("warning", f"Bullet is {n} words; keep bullets under {MAX_BULLET_WORDS} so they fit on 1–2 lines.", b.id)
        elif n < MIN_BULLET_WORDS:
            add("info", "Very short bullet — add what you did and the result.", b.id)
        if WEAK_STARTS.match(b.text):
            add("warning", "Starts with a weak phrase; lead with an action verb (Built, Led, Reduced…).", b.id)
        if PRONOUNS.search(b.text):
            add("info", "Avoid first-person pronouns in bullets.", b.id)
        first = re.sub(r"[^a-z]", "", b.text.split()[0].lower()) if b.text.split() else ""
        if first:
            starts[first] += 1

    for verb, count in starts.items():
        if count >= 3:
            add("info", f'{count} bullets start with "{verb.capitalize()}" — vary the action verbs.')

    endings = Counter(b.text.rstrip()[-1:] == "." for s, _, b in doc.bullets()
                      if s.kind in ("experience", "projects") and b.text.strip())
    if endings[True] and endings[False]:
        add("info", "Some bullets end with a period and some don't — pick one style.")
    return issues
