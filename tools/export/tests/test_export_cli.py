import subprocess
import sys
from pathlib import Path


def test_export_docx_cli_creates_artifact(tmp_path: Path) -> None:
    source = tmp_path / "draft.md"
    output = tmp_path / "draft.docx"
    source.write_text("# Title\n\nBody\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "tools/export/export_docx.py", "--source", str(source), "--output", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip().endswith("draft.docx")
    assert output.is_file()


def test_export_pdf_cli_creates_artifact(tmp_path: Path) -> None:
    source = tmp_path / "draft.md"
    output = tmp_path / "draft.pdf"
    source.write_text("# Title\n\nBody\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "tools/export/export_pdf.py", "--source", str(source), "--output", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip().endswith("draft.pdf")
    assert output.read_bytes().startswith(b"%PDF-")
