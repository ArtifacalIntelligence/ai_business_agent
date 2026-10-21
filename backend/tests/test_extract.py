import io
import pytest
from docx import Document
from app.extract import extract_text


def test_txt():
    assert extract_text("a.txt", b"hello world") == "hello world"


def test_docx():
    d = Document()
    d.add_paragraph("Meeting notes")
    buf = io.BytesIO()
    d.save(buf)
    assert "Meeting notes" in extract_text("n.docx", buf.getvalue())


def test_unsupported_type():
    with pytest.raises(ValueError):
        extract_text("x.png", b"123")