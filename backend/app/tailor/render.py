"""render_resume: ResumeDoc -> ATS-friendly PDF (reportlab) and DOCX (python-docx).

Deterministic on purpose: the LLM never writes the file. Single column, standard
section titles, real text (no images or tables for content) — what ATS parsers
read best.
"""

from __future__ import annotations

import os
from io import BytesIO
from xml.sax.saxutils import escape

from .models import ResumeDoc

# ---- PDF -------------------------------------------------------------------------
_FONT_CANDIDATES = [
    os.environ.get("RESUME_FONT_PATH", ""),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
_LATIN1_FIX = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-",
                             "•": "-", "…": "...", "\u00a0": " ", "→": "->", "✓": "-"})
_fonts: tuple[str, str, bool] | None = None


def _register_fonts() -> tuple[str, str, bool]:
    """(regular, bold, unicode_ok). Uses a TTF if one is around so non-Latin names render."""
    global _fonts
    if _fonts:
        return _fonts
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    for path in _FONT_CANDIDATES:
        if path and os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("ResumeSans", path))
                bold = path.replace("DejaVuSans.ttf", "DejaVuSans-Bold.ttf").replace("arial.ttf", "arialbd.ttf")
                if bold != path and os.path.exists(bold):
                    pdfmetrics.registerFont(TTFont("ResumeSans-Bold", bold))
                    _fonts = ("ResumeSans", "ResumeSans-Bold", True)
                else:
                    _fonts = ("ResumeSans", "ResumeSans", True)
                return _fonts
            except Exception:
                continue
    _fonts = ("Helvetica", "Helvetica-Bold", False)
    return _fonts


def render_pdf(doc: ResumeDoc) -> bytes:
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import HRFlowable, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    regular, bold, unicode_ok = _register_fonts()

    def t(s: str) -> str:
        if not unicode_ok:
            s = s.translate(_LATIN1_FIX).encode("latin-1", "replace").decode("latin-1")
        return escape(s)

    base = ParagraphStyle("base", fontName=regular, fontSize=10, leading=12.6)
    name_s = ParagraphStyle("name", base, fontName=bold, fontSize=17, leading=21, alignment=TA_CENTER)
    contact_s = ParagraphStyle("contact", base, fontSize=9.2, alignment=TA_CENTER, textColor="#333333")
    section_s = ParagraphStyle("section", base, fontName=bold, fontSize=11, leading=14, spaceBefore=7)
    head_s = ParagraphStyle("head", base, fontName=bold)
    date_s = ParagraphStyle("date", base, alignment=2)
    sub_s = ParagraphStyle("sub", base, textColor="#444444")
    bullet_s = ParagraphStyle("bullet", base, leftIndent=0)

    buf = BytesIO()
    pdf = SimpleDocTemplate(buf, pagesize=LETTER, leftMargin=0.6 * inch, rightMargin=0.6 * inch,
                            topMargin=0.5 * inch, bottomMargin=0.5 * inch, title=doc.name or "Resume",
                            author=doc.name)
    width = LETTER[0] - 1.2 * inch
    story: list = []
    if doc.name:
        story.append(Paragraph(t(doc.name), name_s))
    if doc.contact:
        story.append(Paragraph(" | ".join(t(c) for c in doc.contact), contact_s))
    story.append(Spacer(1, 4))

    for s in doc.sections:
        if not any(e.bullets or e.heading for e in s.entries):
            continue
        story.append(Paragraph(t(s.title.upper()), section_s))
        story.append(HRFlowable(width="100%", thickness=0.6, color="#888888", spaceBefore=1, spaceAfter=3))
        for e in s.entries:
            if e.heading or e.dates:
                row = Table([[Paragraph(t(e.heading), head_s), Paragraph(t(e.dates), date_s)]],
                            colWidths=[width * 0.74, width * 0.26])
                row.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                         ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                                         ("VALIGN", (0, 0), (-1, -1), "TOP")]))
                story.append(row)
            if e.subheading:
                story.append(Paragraph(t(e.subheading), sub_s))
            if not e.bullets:
                continue
            if s.kind in ("summary", "skills"):
                story += [Paragraph(t(b.text), base) for b in e.bullets]
            else:
                story.append(ListFlowable(
                    [ListItem(Paragraph(t(b.text), bullet_s), leftIndent=11) for b in e.bullets],
                    bulletType="bullet", start="-" if not unicode_ok else "•", leftIndent=11,
                    bulletFontName=regular, bulletFontSize=9))
            story.append(Spacer(1, 2))
    pdf.build(story)
    return buf.getvalue()


# ---- DOCX ------------------------------------------------------------------------
def render_docx(doc: ResumeDoc) -> bytes:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
    from docx.shared import Inches, Pt

    d = Document()
    for sec in d.sections:
        sec.left_margin = sec.right_margin = Inches(0.6)
        sec.top_margin = sec.bottom_margin = Inches(0.5)
    normal = d.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(0)

    if doc.name:
        p = d.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(doc.name)
        r.bold = True
        r.font.size = Pt(17)
    if doc.contact:
        p = d.add_paragraph(" | ".join(doc.contact))
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    right_tab = Inches(7.3)
    for s in doc.sections:
        if not any(e.bullets or e.heading for e in s.entries):
            continue
        p = d.add_paragraph()
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(s.title.upper())
        r.bold = True
        r.font.size = Pt(11.5)
        for e in s.entries:
            if e.heading or e.dates:
                p = d.add_paragraph()
                p.paragraph_format.tab_stops.add_tab_stop(right_tab, WD_TAB_ALIGNMENT.RIGHT)
                p.paragraph_format.space_before = Pt(3)
                p.add_run(e.heading).bold = True
                if e.dates:
                    p.add_run("\t" + e.dates)
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
