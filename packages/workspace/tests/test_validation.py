from pathlib import Path

from docagent_workspace import create_workspace, validate_workspace


def test_validate_workspace_reports_missing_required_files(tmp_path: Path):
    root = tmp_path / "task-001"
    create_workspace(root, brief="Write a PRD.")

    result = validate_workspace(root)

    assert not result.valid
    assert "context/user_intent.md" in result.missing_files
    assert "context/style_notes.md" in result.missing_files
    assert "context/structure_notes.md" in result.missing_files
    assert "draft/outline.md" in result.missing_files


def test_validate_workspace_passes_when_required_files_exist(tmp_path: Path):
    root = tmp_path / "task-001"
    create_workspace(root, brief="Write a PRD.")
    for path in [
        "context/user_intent.md",
        "context/style_notes.md",
        "context/structure_notes.md",
        "draft/outline.md",
    ]:
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# ok\n", encoding="utf-8")

    result = validate_workspace(root)

    assert result.valid
    assert result.missing_files == []
