"""edit_docx: apply the tailored resume to the user's ORIGINAL .docx, in place.

Rebuilding a resume from text always loses something (a custom template, a
two-tone header, exact spacing). For Word uploads we can do better: find the
paragraph that holds each line of the parsed resume and change only its text,
so every font, color, border and spacing stays exactly as the user made it.

How
  1. Map every field of the original ResumeDoc (name, contact items, section
     titles, entry headings/dates/subheadings, bullets) to the paragraph that
     contains it, walking the document in order.
  2. Diff the final ResumeDoc against the original by id (ids survive tailoring:
     a rewrite keeps the bullet id, added bullets get new ids).
  3. Apply: replace text spans, delete paragraphs, move paragraphs to reorder,
     clone a neighbouring bullet paragraph to add one.

All-or-nothing: if any change can't be applied exactly (a line not found, a
layout we can't safely clone), return None and the caller renders a fresh file
from the style instead. A half-applied edit would be worse than either.
"""

from __future__ import annotations

import logging
import re
from copy import deepcopy
from io import BytesIO

from .models import Entry, ResumeDoc

log = logging.getLogger(__name__)


class _Skip(Exception):
    """This document can't be edited in place; fall back to rendering."""


def _compact(s: str) -> str:
    return re.sub(r"\s+", "", s)


# ---- text spans inside one paragraph -----------------------------------------------------
def _ts(p) -> list:
    from docx.oxml.ns import qn
    return list(p.iter(qn("w:t")))


def _ptext(p) -> str:
    return "".join(t.text or "" for t in _ts(p))


def _preserve(t) -> None:
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")


def replace_span(p, old: str, new: str) -> bool:
    """Replace the first occurrence of `old` (whitespace-insensitive) in paragraph p with `new`,
    keeping the formatting of the run where the span starts. False if `old` isn't there."""
    key = _compact(old)
    if not key:
        return False
    ts = _ts(p)
    chars: list[tuple[int, int]] = []
    for ti, t in enumerate(ts):
        for oi, ch in enumerate(t.text or ""):
            if not ch.isspace():
                chars.append((ti, oi))
    comp = "".join(ts[ti].text[oi] for ti, oi in chars)
    pos = comp.find(key)
    if pos < 0:
        return False
    sti, soi = chars[pos]
    eti, eoi = chars[pos + len(key) - 1]
    if sti == eti:
        t = ts[sti]
        t.text = t.text[:soi] + new + t.text[eoi + 1:]
        _preserve(t)
        return True
    ts[sti].text = ts[sti].text[:soi] + new
    _preserve(ts[sti])
    for t in ts[sti + 1:eti]:
        t.text = ""
    ts[eti].text = ts[eti].text[eoi + 1:]
    _preserve(ts[eti])
    return True


def _clone(p):
    """Deep copy of a paragraph without bookmarks/comment anchors (their ids must stay unique)."""
    from docx.oxml.ns import qn
    c = deepcopy(p)
    for tag in ("w:bookmarkStart", "w:bookmarkEnd", "w:commentRangeStart", "w:commentRangeEnd",
                "w:commentReference", "w:proofErr"):
        for el in list(c.iter(qn(tag))):
            el.getparent().remove(el)
    return c


def _remove(p) -> None:
    from docx.oxml.ns import qn
    parent = p.getparent()
    if parent is None:
        return
    if parent.tag == qn("w:tc") and len(parent.findall(qn("w:p"))) == 1:
        for t in _ts(p):  # a table cell must keep one paragraph
            t.text = ""
        return
    parent.remove(p)


# ---- mapping the original resume onto paragraphs --------------------------------------
class _Map:
    def __init__(self, paras: list, doc: ResumeDoc) -> None:
        self.paras = paras
        self.keys = [_compact(_ptext(p)) for p in paras]
        self.at: dict[str, object] = {}   # field key -> paragraph element
        self.now: dict[str, str] = {}     # field key -> text after step 1 (when it changed)
        self.cursor = 0
        self._walk(doc)

    def _find(self, text: str, exact: bool, start: int | None = None) -> int | None:
        key = _compact(text)
        if not key:
            return None
        for i in range(self.cursor if start is None else start, len(self.paras)):
            k = self.keys[i]
            # exact: the paragraph is this line, plus at most a typed bullet glyph
            if (exact and k.endswith(key) and len(k) - len(key) <= 2) or (not exact and key in k):
                return i
        return None

    def _put(self, field: str, text: str, exact: bool, advance: bool = True) -> None:
        i = self._find(text, exact)
        if i is None:
            return
        self.at[field] = self.paras[i]
        self.cursor = i + 1 if advance else i

    def _walk(self, doc: ResumeDoc) -> None:
        self._put("name", doc.name, exact=False)
        for n, c in enumerate(doc.contact):
            self._put(f"contact.{n}", c, exact=False, advance=False)
        if doc.contact and any(f"contact.{n}" in self.at for n in range(len(doc.contact))):
            self.cursor += 1
        for s in doc.sections:
            self._put(f"{s.id}.title", s.title, exact=True)
            for e in s.entries:
                if e.heading:
                    self._put(f"{e.id}.heading", e.heading, exact=False, advance=False)
                if e.dates:
                    self._put(f"{e.id}.dates", e.dates, exact=False, advance=False)
                for fld in ("heading", "dates"):
                    if f"{e.id}.{fld}" in self.at:
                        self.cursor = max(self.cursor, self.paras.index(self.at[f"{e.id}.{fld}"]) + 1)
                if e.subheading:
                    self._put(f"{e.id}.subheading", e.subheading, exact=False)
                for b in e.bullets:
                    self._put(b.id, b.text, exact=True)

    def get(self, field: str):
        if field not in self.at:
            raise _Skip(f"couldn't find {field}")
        return self.at[field]

    def entry_paras(self, e: Entry) -> list:
        fields = [f"{e.id}.{f}" for f in ("heading", "dates", "subheading")] + [b.id for b in e.bullets]
        out = []
        for f in fields:
            p = self.at.get(f)
            if p is not None and p.getparent() is not None and p not in out:  # skip removed ones
                out.append(p)
        return out


# ---- the edit --------------------------------------------------------------------------
def _set_text(m: _Map, field: str, old: str, new: str) -> None:
    if old == new:
        return
    if not old:
        raise _Skip(f"{field} was empty in the original")
    if not replace_span(m.get(field), old, new):
        raise _Skip(f"text of {field} moved")
    m.now[field] = new


def _consecutive(els: list) -> bool:
    if not els:
        return True
    parent = els[0].getparent()
    if any(e.getparent() is not parent for e in els):
        return False
    idx = sorted(parent.index(e) for e in els)
    return idx == list(range(idx[0], idx[0] + len(idx)))


def _move_in_order(els_in_new_order: list) -> None:
    """els are consecutive siblings; put them back in the given order at the same place."""
    parent = els_in_new_order[0].getparent()
    first = min(parent.index(e) for e in els_in_new_order)
    for e in els_in_new_order:
        parent.remove(e)
    for n, e in enumerate(els_in_new_order):
        parent.insert(first + n, e)


def _apply(d, original: ResumeDoc, final: ResumeDoc) -> None:
    from .style import body_paragraphs

    paras = [p._p for p in body_paragraphs(d)]
    m = _Map(paras, original)

    if [s.id for s in final.sections] != [s.id for s in original.sections]:
        raise _Skip("sections were added, removed or reordered")
    if len(final.contact) != len(original.contact):
        raise _Skip("contact lines changed count")

    # 1. text of fields that exist in both
    _set_text(m, "name", original.name, final.name)
    for n, (a, b) in enumerate(zip(original.contact, final.contact)):
        _set_text(m, f"contact.{n}", a, b)

    plans = []
    for so, sf in zip(original.sections, final.sections):
        _set_text(m, f"{so.id}.title", so.title, sf.title)
        orig_entries = {e.id: e for e in so.entries}
        for ef in sf.entries:
            eo = orig_entries.get(ef.id)
            if eo is None:
                continue
            for fld in ("heading", "dates", "subheading"):
                _set_text(m, f"{ef.id}.{fld}", getattr(eo, fld), getattr(ef, fld))
            orig_b = {b.id: b for b in eo.bullets}
            for b in ef.bullets:
                if b.id in orig_b:
                    _set_text(m, b.id, orig_b[b.id].text, b.text)
        plans.append((so, sf))

    # 2. removals
    for so, sf in plans:
        final_entries = {e.id: e for e in sf.entries}
        for eo in so.entries:
            ef = final_entries.get(eo.id)
            if ef is None:
                needed = [b.id for b in eo.bullets] + [f"{eo.id}.{f}" for f in ("heading", "dates", "subheading")
                                                        if getattr(eo, f)]
                if any(k not in m.at for k in needed):
                    raise _Skip(f"entry {eo.id} isn't fully mapped")
                for p in m.entry_paras(eo):
                    _remove(p)
                continue
            keep = {b.id for b in ef.bullets}
            for b in eo.bullets:
                if b.id not in keep:
                    _remove(m.get(b.id))

    # 3. reorder surviving bullets, then entries
    for so, sf in plans:
        orig_entries = {e.id: e for e in so.entries}
        for ef in sf.entries:
            eo = orig_entries.get(ef.id)
            if eo is None:
                continue
            orig_ids = {b.id for b in eo.bullets}
            new_order = [b.id for b in ef.bullets if b.id in orig_ids]
            old_order = [b.id for b in eo.bullets if b.id in set(new_order)]
            if new_order != old_order:
                els = [m.get(i) for i in new_order]
                if not _consecutive(els):
                    raise _Skip("bullets to reorder aren't next to each other")
                _move_in_order(els)

        survivors = [e.id for e in sf.entries if e.id in orig_entries]
        old = [e.id for e in so.entries if e.id in set(survivors)]
        if survivors != old:
            blocks = {}
            for eid in old:
                ps = m.entry_paras(orig_entries[eid])
                if not ps:
                    raise _Skip("entry to reorder isn't mapped")
                blocks[eid] = ps
            # Each block runs from its first paragraph up to the next block, so spacer
            # paragraphs between entries travel with the entry above them.
            parent = blocks[old[0]][0].getparent()
            starts = [parent.index(blocks[eid][0]) for eid in old]
            if any(p.getparent() is not parent for ps in blocks.values() for p in ps) or starts != sorted(starts):
                raise _Skip("entries aren't simple consecutive blocks")
            ends = starts[1:] + [parent.index(blocks[old[-1]][-1]) + 1]
            full = {eid: list(parent[starts[i]:ends[i]]) for i, eid in enumerate(old)}
            ordered = [el for eid in survivors for el in full[eid]]
            _move_in_order(ordered)

    # 4. additions: bullets into existing entries, and new entries (experience bank)
    def bullet_template(entries: list[Entry]) -> tuple[object, str] | None:
        for e in entries:
            for b in e.bullets:
                if b.id in m.at:
                    return m.at[b.id], m.now.get(b.id, b.text)
        return None

    def last_of(e: Entry):
        ps = m.entry_paras(e)
        return max(ps, key=lambda p: p.getparent().index(p)) if ps else None

    any_entries = [e for s in original.sections if s.kind not in ("summary", "skills") for e in s.entries]
    for so, sf in plans:
        orig_entries = {e.id: e for e in so.entries}
        tail = {e.id: last_of(e) for e in so.entries if e.id in {x.id for x in sf.entries}}

        for ef in sf.entries:
            eo = orig_entries.get(ef.id)
            if eo is None or all(b.id in {x.id for x in eo.bullets} for b in ef.bullets):
                continue
            orig_ids = {b.id for b in eo.bullets}
            tpl = bullet_template([eo] + so.entries + any_entries)
            if tpl is None:
                raise _Skip("no bullet paragraph to copy")
            tpl_p, tpl_text = tpl
            prev = None  # element the next new bullet goes after
            for b in ef.bullets:
                if b.id in orig_ids:
                    prev = m.get(b.id)
                    continue
                new_p = _clone(tpl_p)
                if not replace_span(new_p, tpl_text, b.text):
                    raise _Skip("couldn't fill copied bullet")
                if prev is None:
                    first = next((m.at[x.id] for x in ef.bullets if x.id in orig_ids), None)
                    if first is not None:
                        first.addprevious(new_p)
                    elif tail.get(ef.id) is not None:
                        tail[ef.id].addnext(new_p)
                        tail[ef.id] = new_p
                    else:
                        raise _Skip("nowhere to put new bullet")
                else:
                    prev.addnext(new_p)
                    if prev is tail.get(ef.id):
                        tail[ef.id] = new_p
                prev = new_p

        # whole new entries
        for n, ef in enumerate(sf.entries):
            if ef.id in orig_entries:
                continue
            tpl_e = next((e for e in so.entries if f"{e.id}.heading" in m.at
                          and any(b.id in m.at for b in e.bullets)), None)
            if tpl_e is None:
                raise _Skip("no entry to copy for a new one")
            head_p = m.at[f"{tpl_e.id}.heading"]
            if head_p.getparent().tag.endswith("}tc") or (tpl_e.dates and m.at.get(f"{tpl_e.id}.dates") is not head_p):
                raise _Skip("entry layout uses a table")
            new_head = _clone(head_p)
            if not replace_span(new_head, m.now.get(f"{tpl_e.id}.heading", tpl_e.heading), ef.heading):
                raise _Skip("couldn't fill copied heading")
            if tpl_e.dates and not replace_span(new_head, m.now.get(f"{tpl_e.id}.dates", tpl_e.dates), ef.dates):
                raise _Skip("couldn't fill copied dates")
            tpl_b = next(b for b in tpl_e.bullets if b.id in m.at)
            new_els = [new_head]
            for b in ef.bullets:
                bp = _clone(m.at[tpl_b.id])
                if not replace_span(bp, m.now.get(tpl_b.id, tpl_b.text), b.text):
                    raise _Skip("couldn't fill copied bullet")
                new_els.append(bp)
            # after the previous entry in final order, else before the next one, else after the title
            prev_id = next((x.id for x in reversed(sf.entries[:n]) if tail.get(x.id) is not None), None)
            next_e = next((orig_entries[x.id] for x in sf.entries[n + 1:] if x.id in orig_entries
                           and m.entry_paras(orig_entries[x.id])), None)
            if prev_id is not None:
                anchor = tail[prev_id]
                for el in reversed(new_els):
                    anchor.addnext(el)
            elif next_e is not None:
                first_p = min(m.entry_paras(next_e), key=lambda p: p.getparent().index(p))
                for el in new_els:
                    first_p.addprevious(el)
            elif f"{so.id}.title" in m.at:
                title = m.at[f"{so.id}.title"]
                for el in reversed(new_els):
                    title.addnext(el)
            else:
                raise _Skip("nowhere to put new entry")
            tail[ef.id] = new_els[-1]


def edit_docx(data: bytes, original: ResumeDoc, final: ResumeDoc) -> bytes | None:
    """The user's .docx with the tailored text, or None if it can't be done exactly."""
    from docx import Document

    try:
        d = Document(BytesIO(data))
        _apply(d, original, final)
        buf = BytesIO()
        d.save(buf)
        return buf.getvalue()
    except _Skip as e:
        log.info("docx in-place edit skipped: %s", e)
    except Exception:  # noqa: BLE001 - fall back to the renderer on anything unexpected
        log.exception("docx in-place edit failed")
    return None
