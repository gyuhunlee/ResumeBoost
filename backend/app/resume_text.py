import re
from io import BytesIO

from docx import Document
from pypdf import PdfReader

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def extract_text(data: bytes, content_type: str) -> str:
    if content_type == PDF:
        reader = PdfReader(BytesIO(data))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    elif content_type == DOCX:
        doc = Document(BytesIO(data))
        text = "\n".join(p.text for p in doc.paragraphs)
    else:
        raise ValueError("Only PDF and DOCX files are supported")
    return re.sub(r"\n{3,}", "\n\n", text).strip()