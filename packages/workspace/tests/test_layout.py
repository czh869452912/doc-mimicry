from pathlib import Path

from docagent_workspace import create_workspace, workspace_paths


def test_create_workspace_creates_contract_dirs(tmp_path: Path):
    root = tmp_path / "task-001"

    create_workspace(root, brief="Write a PRD.")

    assert (root / "brief.md").read_text(encoding="utf-8") == "Write a PRD.\n"
    assert (root / "inputs/original").is_dir()
    assert (root / "inputs/markdown").is_dir()
    assert (root / "inputs/assets").is_dir()
    assert (root / "inputs/reports").is_dir()
    assert (root / "context").is_dir()
    assert (root / "draft/sections").is_dir()
    assert (root / "versions").is_dir()
    assert (root / "reviews").is_dir()
    assert (root / "artifacts").is_dir()
    assert (root / "logs").is_dir()


def test_workspace_paths_returns_expected_files(tmp_path: Path):
    paths = workspace_paths(tmp_path / "task-001")

    assert paths.brief == tmp_path / "task-001" / "brief.md"
    assert paths.current_draft == tmp_path / "task-001" / "draft" / "draft.md"
    assert paths.style_notes == tmp_path / "task-001" / "context" / "style_notes.md"
