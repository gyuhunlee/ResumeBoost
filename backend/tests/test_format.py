"""Keeping the original format: style extraction, style-aware rendering, in-place .docx edits.

Run:  cd backend && python -m pytest -q
"""

from io import BytesIO

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

from app.resume_text import extract_text
from app.tailor.docx_edit import edit_docx, replace_span
from app.tailor.models import Bullet, Entry, ResumeDoc
from app.tailor.parse import parse_rules
from app.tailor.render import render_docx, render_pdf
from app.tailor.style import DOCX, PDF, ResumeStyle, extract_style, friendly_font

BULLETS_1 = [
    "Worked on the backend for a booking web app using Postgres and FastAPI.",
    "Helped make deployments faster with GitHub Actions, cutting release time by 40%.",
    "Wrote unit tests for the payments service.",
]


def make_docx(center_name: bool = False) -> bytes:
    """A user's Word resume: Garamond, navy titles, tab-aligned dates, typed bullets."""
    d = Document()
    d.sections[0].left_margin = Inches(0.8)
    normal = d.styles["Normal"]
    normal.font.name = "Garamond"
    normal.font.size = Pt(11)
    p = d.add_paragraph()
    if center_name:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Gyuhun Lee")
    r.bold, r.font.size = True, Pt(22)
    d.add_paragraph("gyuhun@example.com • (530) 555-0101 • linkedin.com/in/gyuhun")

    def title(t: str) -> None:
        p = d.add_paragraph()
        r = p.add_run(t)
        r.bold, r.font.size = True, Pt(13)
        r.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)

    title("Experience")
    p = d.add_paragraph()
    p.add_run("Software Engineer Intern — Acme Corp").bold = True
    p.add_run("\tJun 2024 – Sep 2024")
    d.add_paragraph("Davis, CA")
    for t in BULLETS_1:
        d.add_paragraph("• " + t)
    d.add_paragraph("")
    p = d.add_paragraph()
    p.add_run("Barista — Blue Cup Coffee").bold = True
    p.add_run("\t2022 – 2024")
    d.add_paragraph("• Served 200+ customers per shift in a fast-paced environment.")
    title("Skills")
    d.add_paragraph("Languages: Python, TypeScript, SQL")
    buf = BytesIO()
    d.save(buf)
    return buf.getvalue()


def load():
    data = make_docx()
    text = extract_text(data, DOCX)
    return data, text, parse_rules(text)


def paragraphs(data: bytes) -> list[str]:
    return [p.text for p in Document(BytesIO(data)).paragraphs if p.text.strip()]


# ---- style -------------------------------------------------------------------------
def test_docx_style_is_read():
    data, text, doc = load()
    st = extract_style(data, DOCX, doc, text)
    assert st.source == "docx"
    assert st.font_name == "Garamond" and st.font == "serif"
    assert st.name_size == 22 and st.name_align == "left"
    assert st.heading_size == 13 and st.heading_color == "#1F3864"
    assert st.heading_upper is False          # titles were written "Experience", not "EXPERIENCE"
    assert st.date_align == "right"
    assert st.contact_sep == " • "
    assert st.margin_x == 0.8


def test_pdf_style_round_trips_through_our_renderer():
    _, text, doc = load()
    wanted = ResumeStyle(font="serif", name_size=20, name_align="left", heading_size=12.5, body_size=10.5,
                         heading_upper=False, heading_rule=True, heading_color="#7A1F1F", margin_x=0.75)
    pdf = render_pdf(doc, wanted)
    ptext = extract_text(pdf, PDF)
    st = extract_style(pdf, PDF, parse_rules(ptext), ptext)
    assert st.source == "pdf" and st.font == "serif" and st.font_name == "Times New Roman"
    assert st.name_size == 20 and st.name_align == "left"
    assert st.body_size == 10.5 and st.heading_size == 12.5
    assert st.heading_color == "#7A1F1F" and st.heading_rule
    assert abs(st.margin_x - 0.75) < 0.05
    assert st.date_align == "right"


def test_centered_name_detected_in_pdf():
    _, text, doc = load()
    pdf = render_pdf(doc, ResumeStyle(name_align="center"))
    ptext = extract_text(pdf, PDF)
    assert extract_style(pdf, PDF, parse_rules(ptext), ptext).name_align == "center"


def test_bad_file_falls_back_to_defaults():
    _, text, doc = load()
    st = extract_style(b"not a pdf", PDF, doc, text)
    assert st.body_size == ResumeStyle().body_size  # defaults, no exception


def test_friendly_font_names():
    assert friendly_font("/ABCDEF+TimesNewRomanPS-BoldMT") == "Times New Roman"
    assert friendly_font("/Calibri-Bold") == "Calibri"
    assert friendly_font("/QWERTY+Lato-Regular") == "Lato"


def test_render_keeps_unicode_punctuation_with_builtin_fonts():
    _, _, doc = load()
    text = extract_text(render_pdf(doc, ResumeStyle(font="serif")), PDF)
    assert "Software Engineer Intern — Acme Corp" in text
    assert "Jun 2024 – Sep 2024" in text


def test_render_docx_uses_style():
    _, _, doc = load()
    out = Document(BytesIO(render_docx(doc, ResumeStyle(font_name="Garamond", heading_upper=False,
                                                         heading_color="#1F3864", name_align="left"))))
    assert out.styles["Normal"].font.name == "Garamond"
    texts = [p.text for p in out.paragraphs]
    assert "Experience" in texts and "EXPERIENCE" not in texts
    assert out.paragraphs[0].alignment != WD_ALIGN_PARAGRAPH.CENTER


# ---- in-place .docx edits ------------------------------------------------------------
def test_replace_span_keeps_runs():
    d = Document()
    p = d.add_paragraph()
    p.add_run("Software Engineer").bold = True
    p.add_run(" — Acme\t2024")
    assert replace_span(p._p, "Software Engineer — Acme", "Backend Engineer — Acme Corp")
    assert p.text == "Backend Engineer — Acme Corp\t2024"
    assert p.runs[0].bold and p.runs[0].text == "Backend Engineer — Acme Corp"
    assert not replace_span(p._p, "not there", "x")


def test_docx_untouched_when_nothing_changed():
    data, _, doc = load()
    out = edit_docx(data, doc, doc.model_copy(deep=True))
    assert out is not None and paragraphs(out) == paragraphs(data)


def test_docx_rewrite_reorder_remove_add():
    data, _, doc = load()
    final = doc.model_copy(deep=True)
    exp, skills = final.sections[0], final.sections[1]
    e1 = exp.entries[0]
    b1, b2, _b3 = e1.bullets
    b1.text = "Built the FastAPI + PostgreSQL backend for a booking web app."
    e1.bullets = [b2, b1, Bullet(id="s1e1+u1", text="Added Docker images for local development.")]
    exp.entries.insert(1, Entry(id="s1+c9", heading="Resumeboost — Personal project", dates="2025",
                                bullets=[Bullet(id="s1+c9b1", text="Built a resume tailoring agent.")]))
    skills.entries[0].bullets[0].text = "Languages: Python, TypeScript, SQL, Docker"
    final.contact[0] = "gyuhun.lee@example.com"

    out = edit_docx(data, doc, final)
    assert out is not None
    assert paragraphs(out) == [
        "Gyuhun Lee",
        "gyuhun.lee@example.com • (530) 555-0101 • linkedin.com/in/gyuhun",
        "Experience",
        "Software Engineer Intern — Acme Corp\tJun 2024 – Sep 2024",
        "Davis, CA",
        "• " + BULLETS_1[1],
        "• Built the FastAPI + PostgreSQL backend for a booking web app.",
        "• Added Docker images for local development.",
        "Resumeboost — Personal project\t2025",
        "• Built a resume tailoring agent.",
        "Barista — Blue Cup Coffee\t2022 – 2024",
        "• Served 200+ customers per shift in a fast-paced environment.",
        "Skills",
        "Languages: Python, TypeScript, SQL, Docker",
    ]
    # formatting survived: the cloned heading is bold, titles keep their color and size
    d = Document(BytesIO(out))
    new_head = next(p for p in d.paragraphs if p.text.startswith("Resumeboost"))
    assert new_head.runs[0].bold
    title = next(p for p in d.paragraphs if p.text == "Experience")
    assert title.runs[0].font.color.rgb == RGBColor(0x1F, 0x38, 0x64) and title.runs[0].font.size == Pt(13)


def test_docx_entry_removed_and_reordered():
    data, _, doc = load()
    final = doc.model_copy(deep=True)
    exp = final.sections[0]
    exp.entries = [exp.entries[1], exp.entries[0]]
    out = edit_docx(data, doc, final)
    assert out is not None
    ps = paragraphs(out)
    assert ps.index("Barista — Blue Cup Coffee\t2022 – 2024") < ps.index("Software Engineer Intern — Acme Corp\tJun 2024 – Sep 2024")

    final2 = doc.model_copy(deep=True)
    final2.sections[0].entries = final2.sections[0].entries[:1]
    out2 = edit_docx(data, doc, final2)
    assert out2 is not None and not any("Barista" in p or "200+" in p for p in paragraphs(out2))


def test_docx_falls_back_when_a_line_cant_be_found():
    data, _, doc = load()
    original = doc.model_copy(deep=True)
    original.sections[0].entries[0].bullets[0].text = "A line that isn't in the file at all."
    final = original.model_copy(deep=True)
    final.sections[0].entries[0].bullets[0].text = "Changed"
    assert edit_docx(data, original, final) is None


def test_docx_falls_back_when_sections_change():
    data, _, doc = load()
    final = doc.model_copy(deep=True)
    final.sections = final.sections[:1]
    assert edit_docx(data, doc, final) is None


def test_finalize_document_is_validated():
    from app.schemas import TailorFinalize
    import pytest
    from pydantic import ValidationError

    ok = TailorFinalize.model_validate({"decisions": [], "document": ResumeDoc(name="x").model_dump()})
    assert ok.document is not None and ok.document.name == "x"
    with pytest.raises(ValidationError):
        TailorFinalize.model_validate({"decisions": [], "document": {"name": "x" * 50_000}})
