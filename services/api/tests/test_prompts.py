from pathlib import Path

import pytest

from docagent_api.prompts import _budget_skill_creator_resources, build_prompt_bundle


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


def test_build_prompt_bundle_includes_generic_doc_type_and_workspace_contract(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    workspace = tmp_path / "workspace"
    (repo / "agent" / "system-prompts").mkdir(parents=True)
    (repo / "doc-types" / "memo").mkdir(parents=True)
    workspace.mkdir()
    (repo / "agent" / "system-prompts" / "docagent-core.md").write_text("Core prompt", encoding="utf-8")
    skill_path = repo / "snapshots" / "memo-v001" / "SKILL.md"
    skill_path.parent.mkdir(parents=True)
    skill_path.write_text("# Published Memo Skill\n", encoding="utf-8")

    bundle = build_prompt_bundle(
        repo,
        workspace,
        "task-001",
        "session-001",
        "memo",
        pack_version_id="memo-v001",
        skill_path=skill_path,
    )

    assert "Document type: memo" in bundle.task_instruction
    assert "# Published Memo Skill" in bundle.task_instruction
    assert "doc-types/prd" not in bundle.task_instruction
    for path in ["context/", "draft/", "reviews/", "artifacts/"]:
        assert path in bundle.task_instruction
    assert bundle.doc_type_id == "memo"
    assert bundle.metadata["pack_version_id"] == "memo-v001"
    assert bundle.metadata["skill_path"] == str(skill_path)


def test_build_prompt_bundle_rejects_doc_type_traversal(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    workspace = tmp_path / "workspace"
    (repo / "agent" / "system-prompts").mkdir(parents=True)
    (repo / "doc-types" / "prd").mkdir(parents=True)
    workspace.mkdir()
    (repo / "agent" / "system-prompts" / "docagent-core.md").write_text("Core prompt", encoding="utf-8")
    (repo / "doc-types" / "prd" / "SKILL.md").write_text("# PRD Skill", encoding="utf-8")

    for doc_type_id in ["../prd", "%2e%2e%2fprd", r"..\prd"]:
        with pytest.raises(ValueError, match="Invalid document type id"):
            build_prompt_bundle(repo, workspace, "task-001", "session-001", doc_type_id)


def test_skill_creator_resource_budget_truncates_large_markdown() -> None:
    manifest = {
        "resources": [
            {
                "id": "example-1",
                "group": "examples",
                "status": "ready",
                "summary": "Long example",
                "markdown": " ".join(f"word{i}" for i in range(40)),
            },
            {
                "id": "spec-1",
                "group": "specs",
                "status": "ready",
                "summary": "Short spec",
                "markdown": "spec rules",
            },
        ]
    }

    budgeted = _budget_skill_creator_resources(manifest, budget_words=20)

    assert any("Truncated example-1" in warning for warning in budgeted["budget_warnings"])
    assert all("markdown" not in resource for resource in budgeted["resources"])
    assert any(resource["id"] == "spec-1" for resource in budgeted["resources"])
