"""Experience bank: everything the user has done, not only what's on this resume.

Sources:
  - experience_items rows the user adds in Settings (jobs, projects, skills…)
  - the user's OTHER uploaded resumes (older versions often hold relevant bullets)

search_experience_bank ranks items by keyword overlap — deterministic and cheap.
Bank text is also part of the facts corpus, so content pulled from it passes
verify_claims.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from .keywords import aliases_of, canonical, term_in
from .parse import parse_rules


class BankItem(BaseModel):
    id: str
    kind: str = "project"          # job | project | education | volunteer | skill | other
    title: str = ""
    organization: str = ""
    dates: str = ""
    bullets: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    source: str = "bank"           # bank | resume:<title>

    def text(self) -> str:
        return "\n".join([self.title, self.organization, self.dates, *self.bullets, ", ".join(self.skills)])


def from_rows(rows: list[dict[str, Any]]) -> list[BankItem]:
    return [BankItem(id=f"bank:{r['id']}", kind=r.get("kind") or "project", title=r.get("title") or "",
                     organization=r.get("organization") or "", dates=r.get("dates") or "",
                     bullets=[b for b in r.get("bullets") or [] if b], skills=[s for s in r.get("skills") or [] if s])
            for r in rows]


def from_resumes(resumes: list[dict[str, Any]], exclude_id: str | None) -> list[BankItem]:
    """Each job/project in another resume becomes a bank item."""
    items: list[BankItem] = []
    for r in resumes:
        if r["id"] == exclude_id or not (r.get("content") or "").strip():
            continue
        doc = parse_rules(r["content"])
        for s in doc.sections:
            if s.kind not in ("experience", "projects", "other"):
                continue
            for e in s.entries:
                if e.bullets:
                    items.append(BankItem(
                        id=f"resume:{r['id']}:{e.id}", kind="job" if s.kind == "experience" else "project",
                        title=e.heading, organization=e.subheading, dates=e.dates,
                        bullets=[b.text for b in e.bullets], source=f"resume:{r.get('title') or 'resume'}"))
    return items


def search_experience_bank(items: list[BankItem], query: str, limit: int = 5) -> list[dict]:
    terms = [t for t in re.split(r"[,;]|\band\b|\bor\b", query) if t.strip()] or [query]
    words = {w for w in re.findall(r"[a-z0-9+#./-]{3,}", query.lower())}
    scored = []
    for item in items:
        text = item.text()
        score = 0.0
        for t in terms:
            t = t.strip()
            if term_in(canonical(t), text) or any(term_in(a, text) for a in aliases_of(t)):
                score += 3
        low = text.lower()
        score += sum(1 for w in words if w in low)
        if score > 0:
            scored.append((score, item))
    scored.sort(key=lambda x: -x[0])
    return [{"item_id": i.id, "kind": i.kind, "title": i.title, "organization": i.organization,
             "dates": i.dates, "bullets": {str(n): b for n, b in enumerate(i.bullets)}, "skills": i.skills,
             "source": i.source, "relevance": s} for s, i in scored[:limit]]
