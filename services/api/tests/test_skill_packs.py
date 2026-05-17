from pathlib import Path

import pytest

from docagent_api.skill_packs import (
    bootstrap_seed_skill_packs,
    publish_skill_pack_snapshot,
    validate_skill_pack_draft,
    write_skill_pack_artifact,
)
from docagent_api.state import DocAgentState


def test_bootstrap_seed_prd_pack_creates_published_snapshot(tmp_path: Path) -> None:
    state = DocAgentState(tmp_path / "state")
    bootstrap_seed_skill_packs(state, Path("doc-types"))

    pack = state.get_skill_pack("prd")
    latest = state.get_latest_skill_pack_version("prd")
    assert pack["title"] == "PRD"
    assert latest["version"] == "v001"
    assert (Path(latest["snapshot_path"]) / "SKILL.md").is_file()


def test_validate_skill_pack_blocks_missing_skill(tmp_path: Path) -> None:
    state = DocAgentState(tmp_path / "state")
    state.save_skill_pack({"id": "memo", "title": "Memo", "description": "", "draft_status": "draft"})

    result = validate_skill_pack_draft(state, "memo")

    assert result["status"] == "failed"
    assert "SKILL.md is missing" in result["errors"]


def test_publish_snapshot_is_immutable_after_draft_edit(tmp_path: Path) -> None:
    state = DocAgentState(tmp_path / "state")
    state.save_skill_pack({"id": "memo", "title": "Memo", "description": "", "draft_status": "draft"})
    write_skill_pack_artifact(
        state,
        "memo",
        "SKILL.md",
        "---\nname: memo\ndescription: Use for memos.\n---\n\n# Memo\n",
        "user",
        "Initial skill",
    )
    version = publish_skill_pack_snapshot(state, "memo", "First version")
    write_skill_pack_artifact(
        state,
        "memo",
        "SKILL.md",
        "---\nname: memo\ndescription: Changed.\n---\n\n# Changed\n",
        "user",
        "Edit draft",
    )

    assert "Use for memos." in (Path(version["snapshot_path"]) / "SKILL.md").read_text(encoding="utf-8")


class FailingVersionSaveState(DocAgentState):
    def save_skill_pack_version(self, version: dict) -> None:
        raise RuntimeError("database unavailable")


def test_publish_snapshot_cleans_partial_directory_when_db_save_fails(tmp_path: Path) -> None:
    state = FailingVersionSaveState(tmp_path / "state")
    state.save_skill_pack({"id": "memo", "title": "Memo", "description": "", "draft_status": "draft"})
    write_skill_pack_artifact(
        state,
        "memo",
        "SKILL.md",
        "---\nname: memo\ndescription: Use for memos.\n---\n\n# Memo\n",
        "user",
        "Initial skill",
    )

    with pytest.raises(RuntimeError, match="database unavailable"):
        publish_skill_pack_snapshot(state, "memo", "First version")

    published_dir = state.skill_pack_root("memo") / "published"
    assert not (published_dir / "v001").exists()
    assert not published_dir.exists() or list(published_dir.iterdir()) == []
