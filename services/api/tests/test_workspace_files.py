from pathlib import Path

import pytest

from docagent_api.workspace_files import list_workspace_files, read_workspace_text_file


def test_lists_workspace_files_by_group(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "context").mkdir(parents=True)
    (workspace / "draft").mkdir()
    (workspace / "brief.md").write_text("Brief\n", encoding="utf-8")
    (workspace / "context" / "user_intent.md").write_text("Intent\n", encoding="utf-8")
    (workspace / "draft" / "draft.md").write_text("Draft\n", encoding="utf-8")

    files = list_workspace_files(workspace)

    assert files == [
        {"path": "brief.md", "group": "brief", "kind": "markdown"},
        {"path": "context/user_intent.md", "group": "context", "kind": "markdown"},
        {"path": "draft/draft.md", "group": "draft", "kind": "markdown"},
    ]


def test_reads_text_file_inside_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "draft").mkdir(parents=True)
    (workspace / "draft" / "draft.md").write_text("# Draft\n", encoding="utf-8")

    assert read_workspace_text_file(workspace, "draft/draft.md") == "# Draft\n"


def test_rejects_path_traversal(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(ValueError, match="outside workspace"):
        read_workspace_text_file(workspace, "../secret.md")


def test_rejects_windows_absolute_path(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(ValueError, match="outside workspace"):
        read_workspace_text_file(workspace, "C:\\Windows\\System32\\cmd.exe")
