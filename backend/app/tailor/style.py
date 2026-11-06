"""extract_style: read the look of the user's original resume file.

The tailored resume should look like the one the user uploaded, not like a
generic template. Text extraction throws layout away, so this reads the file
again and keeps just enough to rebuild it: font family, sizes for the name,
section titles and body, alignment, the rule under section titles, the bullet
glyph and the page margins.

Everything here is a best guess. Any failure falls back to the defaults, which
match the previous fixed template, so a strange file never breaks tailoring.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from io import BytesIO
from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from .models import ResumeDoc
from .parse import BULLET_RX, DATE_RX

log = logging.getLogger(__name__)

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

SERIF_RX = re.compile(r"times|garamond|georgia|cambria|book ?antiqua|palatino|minion|serif|baskerville|"
                      r"caslon|didot|bodoni|charter|merriweather|playfair|libre ?baskerville|century", re.I)
# Font names as they appear in PDFs ("TimesNewRomanPSMT", "Calibri-Bold") -> a name CSS and Word know.
_FRIENDLY = [
    (r"timesnewroman|times", "Times New Roman"), (r"garamond", "Garamond"), (r"georgia", "Georgia"),
    (r"cambria", "Cambria"), (r"bookantiqua", "Book Antiqua"), (r"palatino", "Palatino Linotype"),
    (r"calibri", "Calibri"), (r"arial|helvetica", "Arial"), (r"verdana", "Verdana"), (r"tahoma", "Tahoma"),
    (r"segoe", "Segoe UI"), (r"lato", "Lato"), (r"roboto", "Roboto"), (r"opensans", "Open Sans"),
    (r"sourcesans", "Source Sans Pro"), (r"helveticaneue", "Helvetica Neue"), (r"aptos", "Aptos"),
    (r"computermodern|cmr|lmroman", "Latin Modern Roman"), (r"charter", "Charter"), (r"dejavusans", "DejaVu Sans"),
]


class ResumeStyle(BaseModel):
    """Serialized snake_case in the session state, camelCase over the API."""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    source: Literal["pdf", "docx", "text"] = "text"
    font: Literal["serif", "sans"] = "sans"
    font_name: str = ""                  # "Garamond"; empty = renderer default
    name_size: float = 17
    heading_size: float = 11
    body_size: float = 10
    name_align: Literal["left", "center"] = "center"
    heading_bold: bool = True
    heading_upper: bool = True           # show section titles in capitals
    heading_rule: bool = True            # line under each section title
    heading_color: str = ""              # "#1F3864"; empty = text color
    date_align: Literal["right", "inline"] = "right"
    bullet: str = "•"
    contact_sep: str = " | "
    margin_x: float = 0.6                # inches
    margin_y: float = 0.5


# ---- helpers -----------------------------------------------------------------------
def _key(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def friendly_font(raw: str) -> str:
    name = raw.lstrip("/")
    name = name.split("+", 1)[-1]                      # subset prefix "ABCDEF+"
    k = _key(re.split(r"[-,]", name)[0])
    for rx, nice in _FRIENDLY:
        if re.search(rx, k):
            return nice
    base = re.split(r"[-,]", name)[0]
    base = re.sub(r"(PS)?MT$|PS$", "", base)
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", base).strip()[:40]


def _bold(raw: str) -> bool:
    return bool(re.search(r"bold|black|heavy|semibold|demi", raw, re.I))


def _round_half(x: float) -> float:
    return round(x * 2) / 2


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _hex(r: float, g: float, b: float) -> str:
    return "#{:02X}{:02X}{:02X}".format(*(int(_clamp(v, 0, 1) * 255 + 0.5) for v in (r, g, b)))


def _is_colored(hexcolor: str) -> bool:
    """Not black, grey or white (only colored titles are worth keeping)."""
    if not hexcolor or len(hexcolor) != 7:
        return False
    r, g, b = (int(hexcolor[i:i + 2], 16) for i in (1, 3, 5))
    return max(r, g, b) - min(r, g, b) > 40


def text_hints(content: str, doc: ResumeDoc, style: ResumeStyle) -> ResumeStyle:
    """Things the extracted text already tells us: bullet glyph, contact separator, title case."""
    glyphs: Counter[str] = Counter()
    for line in content.splitlines():
        m = BULLET_RX.match(line)
        if m:
            g = m.group(0).strip()
            if g and not g[0].isdigit() and g != "o":
                glyphs[g] += 1
    if glyphs:
        g = glyphs.most_common(1)[0][0]
        style.bullet = {"-": "–", "*": "•", "·": "•", "∙": "•"}.get(g, g)

    head = content.split("\n", 6)[:6]
    for sep, out in (("|", " | "), ("•", " • "), ("·", " · "), ("◆", " ◆ ")):
        if any(sep in ln for ln in head):
            style.contact_sep = out
            break

    titles = [s.title for s in doc.sections if re.search(r"[A-Za-z]", s.title)]
    if titles:
        style.heading_upper = all(t == t.upper() for t in titles)
    return style


# ---- PDF ---------------------------------------------------------------------------
def _mult(a: list[float], b: list[float]) -> list[float]:
    return [a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3],
            a[2] * b[0] + a[3] * b[2], a[2] * b[1] + a[3] * b[3],
            a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5]]


def _pdf_style(data: bytes, doc: ResumeDoc, style: ResumeStyle) -> ResumeStyle:
    from pypdf import PdfReader
    from reportlab.pdfbase.pdfmetrics import stringWidth

    page = PdfReader(BytesIO(data)).pages[0]
    box = page.mediabox
    left, bottom = float(box.left), float(box.bottom)
    width, height = float(box.width), float(box.height)

    chunks: list[dict] = []
    rules = 0
    fill = ["#000000"]
    path_start: list[float] = []

    def before(op: bytes, args: list, cm: list, tm: list) -> None:
        nonlocal rules, path_start
        try:
            if op == b"rg" and len(args) == 3:
                fill[0] = _hex(*(float(a) for a in args))
            elif op == b"g" and len(args) == 1:
                v = float(args[0])
                fill[0] = _hex(v, v, v)
            elif op == b"k" and len(args) == 4:
                c, m, y, k = (float(a) for a in args)
                fill[0] = _hex((1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k))
            elif op == b"re" and len(args) == 4:
                w, h = abs(float(args[2]) * cm[0]), abs(float(args[3]) * cm[3])
                if h < 2.5 and w > width * 0.4:
                    rules += 1
            elif op == b"m" and len(args) == 2:
                path_start = [float(args[0]), float(args[1])]
            elif op == b"l" and len(args) == 2 and path_start:
                dx = abs(float(args[0]) - path_start[0]) * abs(cm[0])
                dy = abs(float(args[1]) - path_start[1]) * abs(cm[3] or 1)
                if dy < 1 and dx > width * 0.4:
                    rules += 1
        except (TypeError, ValueError):
            pass

    def visit(text: str, cm: list, tm: list, font: dict | None, size: float) -> None:
        if not text or not text.strip():
            return
        m = _mult(list(tm), list(cm))
        eff = abs(size) * math.sqrt(abs(m[0] * m[3] - m[1] * m[2])) if size else 0
        if eff < 4 or eff > 60:
            return
        raw = str((font or {}).get("/BaseFont", "")) if font else ""
        chunks.append({"text": text.strip(), "x": m[4] - left, "y": m[5] - bottom, "size": eff,
                       "font": raw, "color": fill[0]})

    page.extract_text(visitor_text=visit, visitor_operand_before=before)
    if not chunks:
        return style

    # body: the size and font carrying the most characters
    sizes: Counter[float] = Counter()
    fonts: Counter[str] = Counter()
    for c in chunks:
        sizes[_round_half(c["size"])] += len(c["text"])
        if c["font"]:
            fonts[friendly_font(c["font"])] += len(c["text"])
    body = sizes.most_common(1)[0][0]
    style.body_size = _clamp(body, 8, 13)
    if fonts:
        style.font_name = fonts.most_common(1)[0][0]
        style.font = "serif" if SERIF_RX.search(style.font_name) else "sans"

    # name: the biggest text near the top of the page
    top = [c for c in chunks if c["y"] > height * 0.72] or chunks
    name = max(top, key=lambda c: c["size"])
    if name["size"] > body * 1.15:
        style.name_size = _clamp(_round_half(name["size"]), 12, 32)
        try:
            w = stringWidth(name["text"], "Helvetica-Bold", name["size"])
        except Exception:
            w = len(name["text"]) * name["size"] * 0.55
        center = name["x"] + w / 2
        style.name_align = "center" if abs(center - width / 2) < width * 0.1 else "left"
    else:
        style.name_size = _clamp(_round_half(body * 1.6), 12, 32)

    # section titles: chunks whose text is one of the parsed titles
    titles = {_key(s.title) for s in doc.sections if _key(s.title)}
    heads = [c for c in chunks if _key(c["text"]) in titles]
    if heads:
        hs = sorted(c["size"] for c in heads)
        style.heading_size = _clamp(_round_half(hs[len(hs) // 2]), 8, 20)
        style.heading_bold = sum(_bold(c["font"]) for c in heads) * 2 >= len(heads)
        colors = Counter(c["color"] for c in heads)
        color = colors.most_common(1)[0][0]
        style.heading_color = color if _is_colored(color) else ""
    style.heading_rule = rules >= 1

    # dates sitting on the right edge
    dates = [c for c in chunks if DATE_RX.fullmatch(c["text"].strip())]
    if dates:
        right = sum(1 for c in dates if c["x"] > width * 0.55)
        style.date_align = "right" if right * 2 >= len(dates) else "inline"

    xs = [c["x"] for c in chunks if c["x"] > 4]
    if xs:
        style.margin_x = round(_clamp(min(xs) / 72, 0.3, 1.25), 2)
    tops = [c["y"] + c["size"] for c in chunks]
    style.margin_y = round(_clamp((height - max(tops)) / 72, 0.3, 1.25), 2)
    return style


# ---- DOCX --------------------------------------------------------------------------
def body_paragraphs(d) -> list:
    """Every paragraph in the main body, including those inside tables, in reading order."""
    from docx.oxml.ns import qn
    from docx.text.paragraph import Paragraph

    return [Paragraph(p, d._body) for p in d.element.body.iter(qn("w:p"))]


def _docx_style(data: bytes, doc: ResumeDoc, style: ResumeStyle) -> ResumeStyle:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn

    d = Document(BytesIO(data))
    normal = d.styles["Normal"].font
    default_size = normal.size.pt if normal.size else 11.0
    default_font = normal.name or ""
    if not default_font:  # theme font lives in docDefaults
        rfonts = d.styles.element.find(f"{qn('w:docDefaults')}/{qn('w:rPrDefault')}/{qn('w:rPr')}/{qn('w:rFonts')}")
        if rfonts is not None:
            default_font = rfonts.get(qn("w:ascii")) or ""
        default_font = default_font or "Calibri"

    def run_size(p, r) -> float:
        if r.font.size:
            return r.font.size.pt
        if p.style is not None and p.style.font.size:
            return p.style.font.size.pt
        return default_size

    def run_font(p, r) -> str:
        return r.font.name or (p.style.font.name if p.style is not None else None) or default_font

    def run_bold(p, r) -> bool:
        if r.bold is not None:
            return bool(r.bold)
        return bool(p.style is not None and p.style.font.bold)

    paras = [p for p in body_paragraphs(d) if p.text.strip()]
    if not paras:
        return style

    sizes: Counter[float] = Counter()
    fonts: Counter[str] = Counter()
    for p in paras:
        for r in p.runs:
            if r.text.strip():
                sizes[_round_half(run_size(p, r))] += len(r.text)
                fonts[run_font(p, r)] += len(r.text)
    if sizes:
        style.body_size = _clamp(sizes.most_common(1)[0][0], 8, 13)
    if fonts:
        style.font_name = friendly_font(fonts.most_common(1)[0][0])
        style.font = "serif" if SERIF_RX.search(style.font_name) else "sans"

    first = paras[0]
    if first.runs:
        style.name_size = _clamp(max(run_size(first, r) for r in first.runs), 12, 32)
    align = first.alignment if first.alignment is not None else (
        first.style.paragraph_format.alignment if first.style is not None else None)
    style.name_align = "center" if align == WD_ALIGN_PARAGRAPH.CENTER else "left"

    titles = {_key(s.title) for s in doc.sections if _key(s.title)}
    heads = [p for p in paras if _key(p.text) in titles]
    if heads:
        hs = sorted(max((run_size(p, r) for r in p.runs), default=default_size) for p in heads)
        style.heading_size = _clamp(hs[len(hs) // 2], 8, 20)
        style.heading_bold = sum(any(run_bold(p, r) for r in p.runs) for p in heads) * 2 >= len(heads)
        if any(r.font.all_caps for p in heads for r in p.runs):
            style.heading_upper = True
        colors = Counter(str(r.font.color.rgb) for p in heads for r in p.runs
                         if r.font.color is not None and r.font.color.type is not None and r.font.color.rgb)
        if colors:
            c = "#" + colors.most_common(1)[0][0].upper()
            style.heading_color = c if _is_colored(c) else ""

        def has_rule(p) -> bool:
            for el in (p._p.pPr, getattr(p.style, "element", None)):
                if el is not None and el.find(f".//{qn('w:pBdr')}/{qn('w:bottom')}") is not None:
                    return True
            nxt = p._p.getnext()  # some templates draw the line as the top border of the next paragraph
            return nxt is not None and nxt.find(f".//{qn('w:pBdr')}/{qn('w:top')}") is not None

        style.heading_rule = sum(has_rule(p) for p in heads) * 2 >= len(heads)

    with_dates = [p for p in paras if DATE_RX.search(p.text)]
    if with_dates:
        right = sum(1 for p in with_dates if "\t" in p.text or p._p.getparent().tag == qn("w:tc"))
        style.date_align = "right" if right * 2 >= len(with_dates) else "inline"

    sec = d.sections[0]
    if sec.left_margin is not None:
        style.margin_x = round(_clamp(sec.left_margin.inches, 0.3, 1.25), 2)
    if sec.top_margin is not None:
        style.margin_y = round(_clamp(sec.top_margin.inches, 0.3, 1.25), 2)
    return style


# ---- entry point -------------------------------------------------------------------
def extract_style(data: bytes | None, content_type: str, doc: ResumeDoc, content: str) -> ResumeStyle:
    style = text_hints(content, doc, ResumeStyle())
    if not data:
        return style
    try:
        if content_type == PDF:
            style.source = "pdf"
            return _pdf_style(data, doc, style)
        if content_type == DOCX:
            style.source = "docx"
            return _docx_style(data, doc, style)
    except Exception as e:  # noqa: BLE001 - a weird file must never break tailoring
        log.warning("style extraction failed (%s); using defaults", e)
    return style


def content_type_for(name: str) -> str:
    return DOCX if name.lower().endswith(".docx") else PDF if name.lower().endswith(".pdf") else ""
