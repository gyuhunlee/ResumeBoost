"""Structured resume + job models shared by every tailoring tool.

Every section is a list of entries and every entry a list of bullets, even the
summary and skills sections (one entry, one bullet per line). That way every
tool can point at any line of the resume with a stable id such as "s2e1b3".
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Literal

from pydantic import BaseModel, Field

SectionKind = Literal["summary", "experience", "projects", "education", "skills", "other"]


class Bullet(BaseModel):
    id: str
    text: str


class Entry(BaseModel):
    id: str
    heading: str = ""      # "Software Engineer Intern — Acme Corp"
    subheading: str = ""   # "Davis, CA" or a tech-stack line
    dates: str = ""        # "Jun 2024 – Sep 2024"
    bullets: list[Bullet] = Field(default_factory=list)


class Section(BaseModel):
    id: str
    title: str
    kind: SectionKind = "other"
    entries: list[Entry] = Field(default_factory=list)


class ResumeDoc(BaseModel):
    name: str = ""
    contact: list[str] = Field(default_factory=list)
    sections: list[Section] = Field(default_factory=list)

    # ---- lookups -------------------------------------------------------------
    def bullets(self) -> Iterator[tuple[Section, Entry, Bullet]]:
        for s in self.sections:
            for e in s.entries:
                for b in e.bullets:
                    yield s, e, b

    def find_bullet(self, bullet_id: str) -> tuple[Section, Entry, Bullet] | None:
        return next((t for t in self.bullets() if t[2].id == bullet_id), None)

    def find_entry(self, entry_id: str) -> tuple[Section, Entry] | None:
        for s in self.sections:
            for e in s.entries:
                if e.id == entry_id:
                    return s, e
        return None

    def find_section(self, section_id: str) -> Section | None:
        return next((s for s in self.sections if s.id == section_id), None)

    def section_of_kind(self, kind: SectionKind) -> Section | None:
        return next((s for s in self.sections if s.kind == kind), None)

    # ---- text views ----------------------------------------------------------
    def text(self) -> str:
        """Plain text, used for keyword matching and as the 'facts' corpus."""
        out = [self.name, *self.contact]
        for s in self.sections:
            out.append(s.title)
            for e in s.entries:
                out += [e.heading, e.subheading, e.dates]
                out += [b.text for b in e.bullets]
        return "\n".join(x for x in out if x)

    def word_count(self) -> int:
        return len(self.text().split())

    def compact(self) -> dict:
        """Small JSON view for the LLM: ids + text only, no empty fields."""
        sections = []
        for s in self.sections:
            entries = []
            for e in s.entries:
                item: dict = {"id": e.id}
                if e.heading:
                    item["heading"] = e.heading
                if e.subheading:
                    item["subheading"] = e.subheading
                if e.dates:
                    item["dates"] = e.dates
                item["bullets"] = {b.id: b.text for b in e.bullets}
                entries.append(item)
            sections.append({"id": s.id, "title": s.title, "kind": s.kind, "entries": entries})
        return {"name": self.name, "sections": sections}

    # ---- ids -----------------------------------------------------------------
    def renumber(self) -> ResumeDoc:
        """Assign ids from position. Only used right after parsing."""
        for si, s in enumerate(self.sections, 1):
            s.id = f"s{si}"
            for ei, e in enumerate(s.entries, 1):
                e.id = f"s{si}e{ei}"
                for bi, b in enumerate(e.bullets, 1):
                    b.id = f"s{si}e{ei}b{bi}"
        return self


class JobAnalysis(BaseModel):
    title: str = ""
    seniority: str = ""                     # intern | entry | mid | senior | lead | ""
    required: list[str] = Field(default_factory=list)     # hard requirements (skills/tools/certs)
    preferred: list[str] = Field(default_factory=list)    # nice-to-haves
    responsibilities: list[str] = Field(default_factory=list)
