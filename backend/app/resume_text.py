"""Text from an uploaded resume (PDF or DOCX).

PDFs don't store lines, only positioned pieces of text. Many resume builders
(Canva, some Word and LaTeX exports, justified text) place every word on its own,
and pypdf's default extraction then puts each word on a new line, which wrecks
everything downstream. So for PDFs we rebuild the lines ourselves: group the
pieces by baseline, order them left to right, and put spaces back from the gaps
between them. A big gap (a right-aligned date) becomes two spaces, and a line
indented past the left margin (a wrapped bullet) keeps a two-space indent, which
the parser uses to join it to the bullet above.
"""

from __future__ import annotations

import logging
import re
from io import BytesIO

from docx import Document
from pypdf import PdfReader

log = logging.getLogger(__name__)

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def extract_text(data: bytes, content_type: str) -> str:
    if content_type == PDF:
        text = ""
        try:
            text = pdf_lines(data)
        except Exception:  # noqa: BLE001 - fall back to pypdf's own extraction
            log.exception("line rebuild failed; using plain extraction")
        if not text.strip():
            reader = PdfReader(BytesIO(data))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
    elif content_type == DOCX:
        doc = Document(BytesIO(data))
        text = "\n".join(p.text for p in doc.paragraphs)
    else:
        raise ValueError("Only PDF and DOCX files are supported")
    return re.sub(r"\n{3,}", "\n\n", normalize_bullets(text)).strip()


# Bullet glyphs as PDF extraction tends to decode them: DEL / WinAnsi 0x95, Symbol and
# Wingdings private-use codes, and the various arrows/boxes resume templates use.
_GLYPHS = "\x7f\x95\u2022\u25cf\u25aa\u25a0\u25e6\u2023\u2043\u2219\u00b7\u27a2\u2756\u25ba\u25b6\u2713\u2714\u2192\u25a1\u25cb"
_BULLET_LINE = re.compile(rf"^(\s*)(?:[{_GLYPHS}]|[\ue000-\uf8ff])\s*")


def normalize_bullets(text: str) -> str:
    """Every bullet line starts with "• ", whatever glyph the PDF used."""
    return "\n".join(_BULLET_LINE.sub(r"\1• ", ln) for ln in text.split("\n"))


def looks_fragmented(text: str) -> bool:
    """True for text where most lines are a single word: the one-word-per-line symptom."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 15:
        return False
    single = sum(1 for ln in lines if len(ln.split()) <= 1)
    return single / len(lines) > 0.4


# ---- PDF line rebuilding --------------------------------------------------------------
def _mult(a: list[float], b: list[float]) -> list[float]:
    return [a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3],
            a[2] * b[0] + a[3] * b[2], a[2] * b[1] + a[3] * b[3],
            a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5]]


def _resolve(x):
    return x.get_object() if hasattr(x, "get_object") else x


def _width(text: str, font: dict | None, size: float) -> float:
    """Width of text in points: the font's own glyph widths when it has them, else an estimate."""
    try:
        if font is not None and "/Widths" in font and "/FirstChar" in font:
            widths = [float(_resolve(w)) for w in _resolve(font["/Widths"])]
            first = int(_resolve(font["/FirstChar"]))
            missing = sum(widths) / len(widths) if widths else 500
            total = 0.0
            for ch in text:
                code = ch.encode("cp1252", errors="replace")[0]
                i = code - first
                total += widths[i] if 0 <= i < len(widths) and widths[i] > 0 else missing
            return total / 1000 * size
    except Exception:  # noqa: BLE001
        pass
    from reportlab.pdfbase.pdfmetrics import stringWidth
    return stringWidth(text, "Helvetica", size)


def _page_chunks(page) -> list[dict]:
    chunks: list[dict] = []

    def visit(text: str, cm: list, tm: list, font: dict | None, size: float) -> None:
        if not text or not text.strip():
            return
        m = _mult(list(tm), list(cm))
        scale_x = abs(m[0]) or abs(m[1]) or 1.0
        scale_y = abs(m[3]) or abs(m[2]) or 1.0
        eff = abs(size) * scale_y if size else 0
        if eff < 3 or eff > 80:
            return
        for k, part in enumerate(text.split("\n")):  # pypdf sometimes hands over several lines at once
            if part.strip():
                lead = len(part) - len(part.lstrip())
                body = part.strip()
                x = m[4] + _width(part[:lead], font, abs(size) * scale_x)
                chunks.append({"text": body, "x": x, "y": m[5] - k * eff * 1.2, "size": eff,
                               "w": _width(body, font, abs(size) * scale_x)})

    page.extract_text(visitor_text=visit)
    return chunks


def _lines_of(chunks: list[dict]) -> list[dict]:
    lines: list[dict] = []
    for c in sorted(chunks, key=lambda c: (-c["y"], c["x"])):
        line = lines[-1] if lines else None
        if line and abs(line["y"] - c["y"]) <= max(1.5, 0.45 * min(line["size"], c["size"])):
            line["chunks"].append(c)
            line["size"] = max(line["size"], c["size"])
        else:
            lines.append({"y": c["y"], "size": c["size"], "chunks": [c]})
    out = []
    for line in lines:
        parts = sorted(line["chunks"], key=lambda c: c["x"])
        text, end = "", None
        for c in parts:
            if end is not None:
                gap = c["x"] - end
                if gap > 2.5 * line["size"]:
                    text = text.rstrip() + "  "
                elif gap > 0.12 * c["size"] and not text.endswith(" "):
                    text += " "
            text += c["text"]
            end = max(end or 0, c["x"] + c["w"])
        out.append({"text": text.strip(), "x": parts[0]["x"], "y": line["y"], "size": line["size"]})
    return out


def pdf_lines(data: bytes) -> str:
    reader = PdfReader(BytesIO(data))
    pages: list[str] = []
    for page in reader.pages:
        lines = _lines_of(_page_chunks(page))
        if not lines:
            continue
        left = min(ln["x"] for ln in lines)
        out: list[str] = []
        prev = None
        for ln in lines:
            if prev is not None and prev["y"] - ln["y"] > 2.0 * max(prev["size"], ln["size"]):
                out.append("")  # a visible gap between blocks
            indent = "  " if ln["x"] - left > 0.9 * ln["size"] else ""
            out.append(indent + ln["text"])
            prev = ln
        pages.append("\n".join(out))
    return "\n".join(pages)
