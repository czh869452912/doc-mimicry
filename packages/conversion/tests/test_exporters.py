import zipfile
from pathlib import Path

from pypdf import PdfReader

from docagent_conversion.exporters import export_markdown_to_docx, export_markdown_to_pdf


def test_export_markdown_to_docx_creates_word_document(tmp_path: Path) -> None:
    source = tmp_path / "draft.md"
    output = tmp_path / "draft.docx"
    source.write_text("# Title\n\nBody text\n", encoding="utf-8")

    result = export_markdown_to_docx(source, output)

    assert result["status"] == "created"
    assert output.is_file()
    with zipfile.ZipFile(output) as archive:
        assert "word/document.xml" in archive.namelist()
        assert "Title" in archive.read("word/document.xml").decode("utf-8")


def test_export_markdown_to_pdf_creates_pdf_file(tmp_path: Path) -> None:
    source = tmp_path / "draft.md"
    output = tmp_path / "draft.pdf"
    source.write_text("# Title\n\nBody text\n", encoding="utf-8")

    result = export_markdown_to_pdf(source, output)

    assert result["status"] == "created"
    assert output.read_bytes().startswith(b"%PDF-")


def test_export_markdown_to_pdf_paginates_long_documents(tmp_path: Path) -> None:
    source = tmp_path / "draft.md"
    output = tmp_path / "draft.pdf"
    source.write_text("\n".join(f"Line {index}" for index in range(120)), encoding="utf-8")

    export_markdown_to_pdf(source, output)

    reader = PdfReader(output)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert len(reader.pages) > 1
    assert "Line 0" in text
    assert "Line 119" in text
