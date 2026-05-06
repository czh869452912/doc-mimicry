from pathlib import Path

from docagent_api.prompts import build_prompt_bundle


def test_build_prompt_bundle_reads_system_prompt_and_skill(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    workspace = tmp_path / "workspace"
    (repo / "agent" / "system-prompts").mkdir(parents=True)
    (repo / "doc-types" / "prd").mkdir(parents=True)
    workspace.mkdir()
    (repo / "agent" / "system-prompts" / "docagent-core.md").write_text("Core prompt", encoding="utf-8")
    (repo / "doc-types" / "prd" / "SKILL.md").write_text("# PRD Skill", encoding="utf-8")

    bundle = build_prompt_bundle(repo, workspace, "task-001", "session-001", "prd")

    assert bundle.system_prompt == "Core prompt"
    assert "# PRD Skill" in bundle.task_instruction
    assert bundle.workspace_root == workspace
    assert bundle.metadata["task_id"] == "task-001"
