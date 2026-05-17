import json
import zipfile
from pathlib import Path

from docagent_conversion import ConversionLayout, convert_resource_bytes


def _docx_bytes(text: str) -> bytes:
    from io import BytesIO

    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>{text}</w:t></w:r></w:p>
  </w:body>
</w:document>"""
    content_types = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


def _layout(root: Path) -> ConversionLayout:
    return ConversionLayout(
        root=root,
        original_dir="inputs/original",
        markdown_dir="inputs/markdown",
        assets_dir="inputs/assets",
        reports_dir="inputs/reports",
    )


def test_converts_markdown_bytes_to_workspace_layout(tmp_path: Path) -> None:
    result = convert_resource_bytes(
        _layout(tmp_path),
        original_filename="brief.md",
        content=b"# Brief\n",
        mime_type="text/markdown",
        created_at="2026-05-17T00:00:00Z",
    )

    assert result["status"] == "converted"
    assert result["source_path"] == "inputs/original/brief.md"
    assert result["markdown_path"] == "inputs/markdown/brief.md"
    assert result["conversion_report_path"] == "inputs/reports/brief.conversion.json"
    assert (tmp_path / result["markdown_path"]).read_text(encoding="utf-8") == "# Brief\n"


def test_converts_html_to_markdown_text(tmp_path: Path) -> None:
    result = convert_resource_bytes(
        _layout(tmp_path),
        original_filename="page.html",
        content=b"<h1>Title</h1><p>Body text</p>",
        mime_type="text/html",
        created_at="2026-05-17T00:00:00Z",
    )

    assert result["status"] == "converted"
    markdown = (tmp_path / result["markdown_path"]).read_text(encoding="utf-8")
    assert "Title" in markdown
    assert "Body text" in markdown


def test_converts_docx_to_markdown_without_keeping_docx_internal(tmp_path: Path) -> None:
    result = convert_resource_bytes(
        _layout(tmp_path),
        original_filename="source.docx",
        content=_docx_bytes("Docx body"),
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        created_at="2026-05-17T00:00:00Z",
    )

    assert result["status"] == "converted"
    assert result["source_path"] == "inputs/original/source.docx"
    assert result["markdown_path"] == "inputs/markdown/source.md"
    assert (tmp_path / result["markdown_path"]).read_text(encoding="utf-8") == "Docx body\n"


def test_converts_digital_pdf_to_markdown(tmp_path: Path) -> None:
    from docagent_conversion.exporters import _simple_pdf_bytes

    result = convert_resource_bytes(
        _layout(tmp_path),
        original_filename="source.pdf",
        content=_simple_pdf_bytes(["PDF body"]),
        mime_type="application/pdf",
        created_at="2026-05-17T00:00:00Z",
    )

    assert result["status"] == "converted"
    assert result["source_path"] == "inputs/original/source.pdf"
    assert result["markdown_path"] == "inputs/markdown/source.md"
    assert "PDF body" in (tmp_path / result["markdown_path"]).read_text(encoding="utf-8")


def test_unsupported_binary_keeps_original_and_failed_report(tmp_path: Path) -> None:
    result = convert_resource_bytes(
        _layout(tmp_path),
        original_filename="deck.pptx",
        content=b"not a supported deck",
        mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        created_at="2026-05-17T00:00:00Z",
    )

    assert result["status"] == "failed"
    assert result["markdown_path"] is None
    assert (tmp_path / "inputs/original/deck.pptx").read_bytes() == b"not a supported deck"
    report = json.loads((tmp_path / result["conversion_report_path"]).read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert report["warnings"][0]["type"] == "unsupported_format"
