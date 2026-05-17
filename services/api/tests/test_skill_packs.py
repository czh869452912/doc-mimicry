from pathlib import Path

import pytest

from docagent_api.skill_packs import (
    bootstrap_seed_skill_packs,
    draft_root,
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


def test_validate_skill_pack_checks_warning_status_resources_for_source_copy(tmp_path: Path) -> None:
    state = DocAgentState(tmp_path / "state")
    state.save_skill_pack({"id": "memo", "title": "Memo", "description": "", "draft_status": "draft"})
    root = draft_root(state, "memo")
    markdown = root / "examples" / "markdown" / "source.md"
    markdown.parent.mkdir(parents=True, exist_ok=True)
    copied_sentence = (
        "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima mike "
        "november oscar papa quebec romeo sierra tango uniform victor whiskey xray yankee zulu"
    )
    markdown.write_text(copied_sentence, encoding="utf-8")
    (root / "SKILL.md").write_text(f"# Memo\n\n{copied_sentence}\n", encoding="utf-8")
    state.save_skill_pack_resource({
        "id": "resource-1",
        "pack_id": "memo",
        "group": "examples",
        "original_filename": "source.docx",
        "source_path": "examples/original/source.docx",
        "markdown_path": "examples/markdown/source.md",
        "conversion_report_path": "examples/reports/source.conversion.json",
        "status": "warning",
        "summary": "",
        "warnings": [{"type": "format_loss", "message": "DOCX formatting was simplified.", "location": None}],
    })

    result = validate_skill_pack_draft(state, "memo")

    assert any("shares 25+ consecutive words" in warning for warning in result["warnings"])


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
