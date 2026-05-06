from pathlib import Path

from docagent_workspace import checkpoint_draft, create_workspace


def test_checkpoint_draft_creates_first_version(tmp_path: Path):
    root = tmp_path / "task-001"
    create_workspace(root, brief="Write a PRD.")
    (root / "draft" / "draft.md").write_text("# Draft\n", encoding="utf-8")

    version = checkpoint_draft(root, summary="Initial draft")

    assert version.version == "v001"
    assert version.version_path == "versions/v001.md"
    assert (root / "versions" / "v001.md").read_text(encoding="utf-8") == "# Draft\n"


def test_checkpoint_draft_increments_versions(tmp_path: Path):
    root = tmp_path / "task-001"
    create_workspace(root, brief="Write a PRD.")
    (root / "draft" / "draft.md").write_text("# Draft 1\n", encoding="utf-8")
    checkpoint_draft(root, summary="Initial draft")
    (root / "draft" / "draft.md").write_text("# Draft 2\n", encoding="utf-8")

    version = checkpoint_draft(root, summary="Second draft")

    assert version.version == "v002"
    assert version.version_path == "versions/v002.md"
    assert (root / "versions" / "v002.md").read_text(encoding="utf-8") == "# Draft 2\n"


def test_checkpoint_requires_current_draft(tmp_path: Path):
    root = tmp_path / "task-001"
    create_workspace(root, brief="Write a PRD.")

    try:
        checkpoint_draft(root, summary="Missing draft")
    except FileNotFoundError as exc:
        assert "draft/draft.md" in str(exc)
    else:
        raise AssertionError("Expected FileNotFoundError")


def test_checkpoint_default_created_at_is_current_utc_timestamp(tmp_path: Path):
    root = tmp_path / "task-001"
    create_workspace(root, brief="Write a PRD.")
    (root / "draft" / "draft.md").write_text("# Draft\n", encoding="utf-8")

    version = checkpoint_draft(root, summary="Initial draft")

    assert version.created_at.endswith("Z")
    assert version.created_at != "1970-01-01T00:00:00Z"
