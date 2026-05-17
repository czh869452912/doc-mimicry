import json
import zipfile
from io import BytesIO
from pathlib import Path

from convert_to_markdown import convert_file


def _docx_bytes(text: str) -> bytes:
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


def test_convert_markdown_copies_to_markdown_dir(tmp_path: Path):
    source = tmp_path / "original" / "note.md"
    source.parent.mkdir()
    source.write_text("# Note\n", encoding="utf-8")
    output_root = tmp_path / "inputs"

    report_path = convert_file(source, output_root)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "succeeded"
    assert Path(report["markdown_path"]).name == "note.md"
    assert (output_root / "original" / "note.md").is_file()
    assert (output_root / "markdown" / "note.md").read_text(encoding="utf-8").strip() == "# Note"


def test_convert_text_wraps_plain_text_as_markdown(tmp_path: Path):
    source = tmp_path / "original" / "note.txt"
    source.parent.mkdir()
    source.write_text("hello\n", encoding="utf-8")
    output_root = tmp_path / "inputs"

    report_path = convert_file(source, output_root)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "succeeded"
    assert (output_root / "markdown" / "note.md").read_text(encoding="utf-8").strip() == "hello"


def test_convert_docx_uses_shared_word_boundary(tmp_path: Path):
    source = tmp_path / "original" / "source.docx"
    source.parent.mkdir()
    source.write_bytes(_docx_bytes("Word body"))
    output_root = tmp_path / "inputs"

    report_path = convert_file(source, output_root)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "succeeded_with_warnings"
    assert report["warnings"][0]["type"] == "docx_format_loss"
    assert (output_root / "original" / "source.docx").is_file()
    assert (output_root / "markdown" / "source.md").read_text(encoding="utf-8").strip() == "Word body"


def test_unsupported_file_writes_failure_report(tmp_path: Path):
    source = tmp_path / "original" / "deck.pptx"
    source.parent.mkdir()
    source.write_bytes(b"not really a pptx")
    output_root = tmp_path / "inputs"

    report_path = convert_file(source, output_root)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert report["markdown_path"] is None
    assert report["warnings"][0]["type"] == "unsupported_format"
