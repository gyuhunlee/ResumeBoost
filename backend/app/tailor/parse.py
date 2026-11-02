"""parse_resume: plain resume text -> ResumeDoc with stable bullet ids.

The LLM is better at messy PDF text (two-column layouts, wrapped lines), but it
can also quietly "improve" wording while parsing. So the LLM result is only
used if every bullet it returns can be found in the original text; otherwise
the rule-based parser wins.
"""

from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher

from pydantic import ValidationError

from .llm import LLM, LLMError
from .models import Bullet, Entry, ResumeDoc, Section, SectionKind

log = logging.getLogger(__name__)

SECTION_TITLES: dict[SectionKind, tuple[str, ...]] = {
    "summary": ("summary", "professional summary", "profile", "objective", "about me", "career objective"),
    "experience": ("experience", "work experience", "professional experience", "employment",
                   "employment history", "work history", "relevant experience", "internships"),
    "projects": ("projects", "personal projects", "academic projects", "selected projects", "portfolio"),
    "education": ("education", "academic background", "education and training"),
    "skills": ("skills", "technical skills", "core competencies", "competencies", "technologies",
               "tools", "skills & interests", "skills and interests", "certifications & skills"),
    "other": ("certifications", "certificates", "licenses", "licenses and certifications", "awards",
              "honors", "activities", "leadership", "volunteer", "volunteer experience",
              "publications", "languages", "interests", "extracurricular activities"),
}
_TITLE_TO_KIND = {t: k for k, ts in SECTION_TITLES.items() for t in ts}

BULLET_RX = re.compile(r"^\s*(?:[•●▪◦‣∙·\-–—*]|o(?=\s)|\d+[.)])\s+")
MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
DATE_RX = re.compile(
    rf"((?:{MONTH}\s+)?(?:19|20)\d\d\s*(?:[-–—]|to)\s*(?:(?:{MONTH}\s+)?(?:19|20)\d\d|present|current|now)"
    rf"|(?:{MONTH}\s+)?(?:19|20)\d\d)\s*$",
    re.I,
)
CONTACT_RX = re.compile(r"@|https?://|linkedin|github\.com|\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}|\|", re.I)


def _kind_for(line: str) -> SectionKind | None:
    t = re.sub(r"[:\s]+$", "", line.strip()).lower()
    t = re.sub(r"\s+", " ", t)
    if t in _TITLE_TO_KIND:
        return _TITLE_TO_KIND[t]
    # ALL-CAPS short line that isn't a contact line, e.g. "RELEVANT COURSEWORK"
    letters = re.sub(r"[^A-Za-z]", "", line)
    if 3 <= len(letters) and line.strip().isupper() and len(line.split()) <= 4 and not CONTACT_RX.search(line):
        return "other"
    return None


def parse_rules(text: str) -> ResumeDoc:
    lines = [ln.rstrip() for ln in text.replace("\r", "").split("\n")]
    doc = ResumeDoc()
    section: Section | None = None
    entry: Entry | None = None

    def new_entry(heading: str = "") -> Entry:
        nonlocal entry
        dates = ""
        if m := DATE_RX.search(heading):
            dates = m.group(1).strip()
            heading = heading[: m.start()].rstrip(" ,|–—-\t")
        entry = Entry(id="", heading=heading.strip(), dates=dates)
        assert section is not None
        section.entries.append(entry)
        return entry

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        kind = _kind_for(line)
        if kind:
            section = Section(id="", title=re.sub(r"[:\s]+$", "", line), kind=kind)
            doc.sections.append(section)
            entry = None
            continue
        if section is None:  # header block: name, then contact lines
            if not doc.name and not CONTACT_RX.search(line):
                doc.name = line
            else:
                doc.contact += [p.strip() for p in re.split(r"\s*[|•·]\s*", line) if p.strip()]
            continue

        is_bullet = bool(BULLET_RX.match(line))
        body = BULLET_RX.sub("", line).strip()

        if section.kind in ("summary", "skills"):
            entry = entry or new_entry()
            if not is_bullet and entry.bullets and section.kind == "summary" and not entry.bullets[-1].text.endswith("."):
                entry.bullets[-1].text += " " + body  # wrapped summary line
            else:
                entry.bullets.append(Bullet(id="", text=body))
            continue

        if is_bullet:
            entry = entry or new_entry()
            entry.bullets.append(Bullet(id="", text=body))
        elif entry and entry.bullets and body[:1].islower():
            entry.bullets[-1].text += " " + body  # PDF line wrap inside a bullet
        elif entry and not entry.bullets and not entry.subheading:
            if not entry.dates and (m := DATE_RX.search(body)):
                entry.dates = m.group(1).strip()
                body = body[: m.start()].rstrip(" ,|–—-\t")
            if body:
                entry.subheading = body
        else:
            new_entry(body)

    return doc.renumber()


LLM_PROMPT = """Split this resume into structured JSON. COPY TEXT EXACTLY as written —
do not fix, shorten, merge or reword anything. Join lines that a PDF wrapped in the
middle of a sentence. Return JSON only:

{{"name": str, "contact": [str],
  "sections": [{{"title": str,
                "kind": "summary"|"experience"|"projects"|"education"|"skills"|"other",
                "entries": [{{"heading": str, "subheading": str, "dates": str, "bullets": [str]}}]}}]}}

For summary and skills sections use one entry with an empty heading and one bullet per line.
For jobs, heading = "Title — Company" as written, dates = the date range as written.

Resume:
{text}"""


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def _faithful(doc: ResumeDoc, source: str) -> bool:
    src = _norm(source)
    for _, _, b in doc.bullets():
        n = _norm(b.text)
        if not n or n in src:
            continue
        # allow tiny differences (ligatures, quotes) but not rewording
        best = max((SequenceMatcher(None, n, src[i:i + len(n)]).ratio()
                    for i in range(0, max(1, len(src) - len(n) + 1), max(1, len(n) // 4))), default=0)
        if best < 0.9:
            log.info("LLM parse changed a bullet, falling back to rules: %r", b.text[:80])
            return False
    return True


def parse_resume(text: str, llm: LLM | None = None) -> ResumeDoc:
    rules = parse_rules(text)
    if llm is None:
        return rules
    try:
        data = llm.generate_json(LLM_PROMPT.format(text=text[:15000]))
        doc = ResumeDoc(
            name=data.get("name") or "",
            contact=[c for c in data.get("contact") or [] if c],
            sections=[
                Section(id="", title=s.get("title") or "", kind=s.get("kind") if s.get("kind") in SECTION_TITLES else "other",
                        entries=[Entry(id="", heading=e.get("heading") or "", subheading=e.get("subheading") or "",
                                       dates=e.get("dates") or "",
                                       bullets=[Bullet(id="", text=b) for b in e.get("bullets") or [] if str(b).strip()])
                                 for e in s.get("entries") or []])
                for s in data.get("sections") or []
            ],
        ).renumber()
    except (LLMError, ValidationError, AttributeError, TypeError) as e:
        log.warning("LLM parse failed, using rules: %s", e)
        return rules
    if not any(True for _ in doc.bullets()) or not _faithful(doc, text):
        return rules
    return doc
