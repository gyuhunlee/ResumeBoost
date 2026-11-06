"""render_resume: ResumeDoc + ResumeStyle -> ATS-friendly PDF (reportlab) and DOCX (python-docx).

Deterministic on purpose: the LLM never writes the file. The layout follows the
style read from the user's original resume (fonts, sizes, alignment, rules,
margins) so the tailored file looks like theirs. It stays single column with
real text (no images, no tables for content) — what ATS parsers read best.

When the original was a .docx, routes_tailor first tries docx_edit, which
changes the user's own file in place; this renderer is the fallback for that
and the only path for PDF originals.
"""

from __future__ import annotations

import os
from io import BytesIO
from xml.sax.saxutils import escape

from .models import ResumeDoc
from .style import ResumeStyle

# ---- PDF -------------------------------------------------------------------------
_FONT_DIRS = ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu", "/usr/share/fonts/TTF"]
# The 14 built-in PDF fonts use WinAnsi (cp1252): fine for • – — “ ” … but not arrows or checks.
_WINANSI_FIX = str.maketrans({"\u00a0": " ", "→": "->", "✓": "-", "▪": "•", "●": "•", "◦": "•", "‣": "•"})
_registered: dict[str, tuple[str, str] | None] = {}


def _ttf(family: str) -> tuple[str, str] | None:
    """Register DejaVu Sans / Serif (if installed) for text that isn't Latin-1. (regular, bold) names."""
    if family in _registered:
        return _registered[family]
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    base = "DejaVuSerif" if family == "serif" else "DejaVuSans"
    dirs = [os.environ.get("RESUME_FONT_DIR", "")] + _FONT_DIRS
    for d in dirs:
        reg = os.path.join(d, f"{base}.ttf")
        if d and os.path.exists(reg):
            try:
                pdfmetrics.registerFont(TTFont(f"R-{base}", reg))
                bold = os.path.join(d, f"{base}-Bold.ttf")
                if os.path.exists(bold):
                    pdfmetrics.registerFont(TTFont(f"R-{base}-Bold", bold))
                    _registered[family] = (f"R-{base}", f"R-{base}-Bold")
                else:
                    _registered[family] = (f"R-{base}", f"R-{base}")
                return _registered[family]
            except Exception:
                continue
    _registered[family] = None
    return None


def _needs_unicode(doc: ResumeDoc) -> bool:
    try:
        doc.text().translate(_WINANSI_FIX).encode("cp1252")
        return False
    except UnicodeEncodeError:
        return True


def _pdf_fonts(doc: ResumeDoc, style: ResumeStyle) -> tuple[str, str, bool]:
    """(regular, bold, unicode_ok). Built-in Times/Helvetica look closest to the usual resume
    fonts; a TTF is only used when the text has characters those can't show (e.g. Hangul)."""
    if _needs_unicode(doc) and (ttf := _ttf(style.font)):
        return ttf[0], ttf[1], True
    if style.font == "serif":
        return "Times-Roman", "Times-Bold", False
    return "Helvetica", "Helvetica-Bold", False


def render_pdf(doc: ResumeDoc, style: ResumeStyle | None = None) -> bytes:
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import HRFlowable, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    st = style or ResumeStyle()
    regular, bold, unicode_ok = _pdf_fonts(doc, st)

    def t(s: str) -> str:
        if not unicode_ok:
            s = s.translate(_WINANSI_FIX).encode("cp1252", "replace").decode("cp1252")
        return escape(s)

    size = st.body_size
    lead = round(size * 1.26, 2)
    color = st.heading_color or "#000000"
    base = ParagraphStyle("base", fontName=regular, fontSize=size, leading=lead)
    name_s = ParagraphStyle("name", base, fontName=bold, fontSize=st.name_size, leading=st.name_size * 1.22,
                            alignment=TA_CENTER if st.name_align == "center" else TA_LEFT)
    contact_s = ParagraphStyle("contact", base, fontSize=max(size - 0.8, 7), textColor="#333333",
                               alignment=TA_CENTER if st.name_align == "center" else TA_LEFT)
    section_s = ParagraphStyle("section", base, fontName=bold if st.heading_bold else regular,
                               fontSize=st.heading_size, leading=st.heading_size * 1.27, spaceBefore=7,
                               textColor=color)
    head_s = ParagraphStyle("head", base, fontName=bold)
    date_s = ParagraphStyle("date", base, alignment=TA_RIGHT)
    sub_s = ParagraphStyle("sub", base, textColor="#444444")
    bullet_s = ParagraphStyle("bullet", base, leftIndent=0)

    buf = BytesIO()
    mx, my = st.margin_x * inch, st.margin_y * inch
    pad = 6  # reportlab frames keep 6pt padding; take it out of the margin so text sits exactly at mx
    pdf = SimpleDocTemplate(buf, pagesize=LETTER, leftMargin=mx - pad, rightMargin=mx - pad, topMargin=my - pad,
                            bottomMargin=my - pad, title=doc.name or "Resume", author=doc.name)
    width = LETTER[0] - 2 * mx
    story: list = []
    if doc.name:
        story.append(Paragraph(t(doc.name), name_s))
    if doc.contact:
        story.append(Paragraph(t(st.contact_sep).join(t(c) for c in doc.contact), contact_s))
    story.append(Spacer(1, 4))

    # Built-in fonts use WinAnsi, which has • and – but not ▪ ● ◦ ‣.
    glyph = st.bullet if unicode_ok or st.bullet in ("•", "–", "-", "·") else "•"

    for s in doc.sections:
        if not any(e.bullets or e.heading for e in s.entries):
            continue
        story.append(Paragraph(t(s.title.upper() if st.heading_upper else s.title), section_s))
        if st.heading_rule:
            story.append(HRFlowable(width="100%", thickness=0.6, color=st.heading_color or "#888888",
                                    spaceBefore=1, spaceAfter=3))
        else:
            story.append(Spacer(1, 2))
        for e in s.entries:
            if e.heading or e.dates:
                if st.date_align == "right" and e.dates:
                    row = Table([[Paragraph(t(e.heading), head_s), Paragraph(t(e.dates), date_s)]],
                                colWidths=[width * 0.74, width * 0.26], hAlign="LEFT")
                    row.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                             ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                                             ("VALIGN", (0, 0), (-1, -1), "TOP")]))
                    story.append(row)
                else:
                    tail = f'<font name="{regular}">{t(st.contact_sep)}{t(e.dates)}</font>' if e.dates else ""
                    story.append(Spacer(1, 2))
                    story.append(Paragraph(t(e.heading) + tail, head_s))
            if e.subheading:
                story.append(Paragraph(t(e.subheading), sub_s))
            if not e.bullets:
                continue
            if s.kind in ("summary", "skills"):
                story += [Paragraph(t(b.text), base) for b in e.bullets]
            else:
                story.append(ListFlowable(
                    [ListItem(Paragraph(t(b.text), bullet_s), leftIndent=11) for b in e.bullets],
                    bulletType="bullet", start=glyph, leftIndent=11,
                    bulletFontName=regular, bulletFontSize=size - 1))
            story.append(Spacer(1, 2))
    pdf.build(story)
    return buf.getvalue()


# ---- DOCX ------------------------------------------------------------------------
def _bottom_border(paragraph, color: str) -> None:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    ppr = paragraph._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    for k, v in (("w:val", "single"), ("w:sz", "6"), ("w:space", "1"), ("w:color", (color or "#888888").lstrip("#"))):
        bottom.set(qn(k), v)
    bdr.append(bottom)
    ppr.append(bdr)


def render_docx(doc: ResumeDoc, style: ResumeStyle | None = None) -> bytes:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor

    st = style or ResumeStyle()
    d = Document()
    for sec in d.sections:
        sec.left_margin = sec.right_margin = Inches(st.margin_x)
        sec.top_margin = sec.bottom_margin = Inches(st.margin_y)
    font = st.font_name or ("Times New Roman" if st.font == "serif" else "Calibri")
    normal = d.styles["Normal"]
    normal.font.name = font
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), font)
    normal.font.size = Pt(st.body_size)
    normal.paragraph_format.space_after = Pt(0)
    for name in ("List Bullet",):
        d.styles[name].font.name = font
    heading_rgb = RGBColor.from_string(st.heading_color.lstrip("#")) if st.heading_color else None
    center = st.name_align == "center"

    if doc.name:
        p = d.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER if center else WD_ALIGN_PARAGRAPH.LEFT
        r = p.add_run(doc.name)
        r.bold = True
        r.font.size = Pt(st.name_size)
    if doc.contact:
        p = d.add_paragraph(st.contact_sep.join(doc.contact))
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER if center else WD_ALIGN_PARAGRAPH.LEFT

    right_tab = Inches(8.5 - 2 * st.margin_x)
    for s in doc.sections:
        if not any(e.bullets or e.heading for e in s.entries):
            continue
        p = d.add_paragraph()
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(s.title.upper() if st.heading_upper else s.title)
        r.bold = st.heading_bold
        r.font.size = Pt(st.heading_size)
        if heading_rgb:
            r.font.color.rgb = heading_rgb
        if st.heading_rule:
            _bottom_border(p, st.heading_color)
        for e in s.entries:
            if e.heading or e.dates:
                p = d.add_paragraph()
                p.paragraph_format.space_before = Pt(3)
                p.add_run(e.heading).bold = True
                if e.dates and st.date_align == "right":
                    p.paragraph_format.tab_stops.add_tab_stop(right_tab, WD_TAB_ALIGNMENT.RIGHT)
                    p.add_run("\t" + e.dates)
                elif e.dates:
                    p.add_run(st.contact_sep + e.dates)
            if e.subheading:
                d.add_paragraph(e.subheading).runs[0].italic = True
            for b in e.bullets:
                if s.kind in ("summary", "skills"):
                    d.add_paragraph(b.text)
                else:
                    d.add_paragraph(b.text, style="List Bullet")

    buf = BytesIO()
    d.save(buf)
    return buf.getvalue()
