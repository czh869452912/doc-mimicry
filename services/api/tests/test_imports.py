from pathlib import Path

from docagent_api.imports import import_text_input


def test_import_text_input_writes_original_markdown_and_report(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"

    result = import_text_input(
        workspace_root=workspace,
        name="notes.txt",
        content="User research notes",
        created_at="2026-04-30T00:00:00Z",
    )

    assert result["status"] == "converted"
    assert result["source_path"] == "inputs/original/notes.txt"
    assert result["markdown_path"] == "inputs/markdown/notes.md"
    assert (workspace / "inputs" / "original" / "notes.txt").read_text(encoding="utf-8") == "User research notes\n"
    assert (workspace / "inputs" / "markdown" / "notes.md").read_text(encoding="utf-8") == "User research notes\n"
    assert (workspace / "inputs" / "reports" / "notes.json").exists()
