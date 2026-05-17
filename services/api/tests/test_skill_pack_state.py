from pathlib import Path

from docagent_api.state import DocAgentState


def test_skill_pack_rows_roundtrip(pg_state: DocAgentState) -> None:
    pg_state.save_skill_pack({
        "id": "risk-report",
        "title": "Risk Report",
        "description": "Enterprise risk review pack",
        "draft_status": "draft",
    })

    assert pg_state.get_skill_pack("risk-report")["title"] == "Risk Report"
    assert pg_state.list_skill_packs()[0]["id"] == "risk-report"


def test_skill_pack_version_rows_are_queryable(pg_state: DocAgentState, tmp_path: Path) -> None:
    pg_state.save_skill_pack({
        "id": "prd",
        "title": "PRD",
        "description": "Product requirements",
        "draft_status": "draft",
    })
    pg_state.save_skill_pack_version({
        "id": "prd-v001",
        "pack_id": "prd",
        "version": "v001",
        "snapshot_path": str(tmp_path / "snapshot"),
        "manifest": {"skill_path": "SKILL.md"},
        "validation": {"status": "passed", "warnings": []},
        "publish_note": "Seed version",
    })

    latest = pg_state.get_latest_skill_pack_version("prd")
    assert latest["id"] == "prd-v001"
    assert latest["version"] == "v001"
