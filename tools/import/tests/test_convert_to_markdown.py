import json
from pathlib import Path

from convert_to_markdown import convert_file


def test_convert_markdown_copies_to_markdown_dir(tmp_path: Path):
    source = tmp_path / "original" / "note.md"
    source.parent.mkdir()
    source.write_text("# Note\n", encoding="utf-8")
    output_root = tmp_path / "inputs"

    report_path = convert_file(source, output_root)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "succeeded"
    assert Path(report["markdown_path"]).name == "note.md"
    assert (output_root / "markdown" / "note.md").read_text(encoding="utf-8") == "# Note\n"


def test_convert_text_wraps_plain_text_as_markdown(tmp_path: Path):
    source = tmp_path / "original" / "note.txt"
    source.parent.mkdir()
    source.write_text("hello\n", encoding="utf-8")
    output_root = tmp_path / "inputs"

    report_path = convert_file(source, output_root)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "succeeded"
    assert (output_root / "markdown" / "note.md").read_text(encoding="utf-8") == "hello\n"


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
