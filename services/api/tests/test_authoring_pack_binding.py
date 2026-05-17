from pathlib import Path

from fastapi.testclient import TestClient

from docagent_api.app import create_app
from docagent_contracts import RuntimeOperationResult, RuntimeSessionState


def test_task_creation_binds_latest_published_pack_version(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))

    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Write a PRD"}).json()

    assert task["doc_type_id"] == "prd"
    assert task["pack_version_id"] == "prd-v001"


def test_task_creation_accepts_explicit_pack_version(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))
    client.post("/skill-packs", json={"id": "memo", "title": "Memo", "description": ""})
    client.put("/skill-packs/memo/artifacts", json={
        "path": "SKILL.md",
        "content": "---\nname: memo\ndescription: Use for memos.\n---\n\n# Memo\n",
        "summary": "Initial memo skill",
    })
    version = client.post("/skill-packs/memo/publish", json={"publish_note": "Memo v1"}).json()

    task = client.post("/tasks", json={
        "doc_type_id": "memo",
        "pack_version_id": version["id"],
        "brief": "Write a memo",
    }).json()

    assert task["pack_version_id"] == version["id"]


def test_authoring_session_uses_published_snapshot_after_draft_changes(tmp_path: Path) -> None:
    class CapturingAdapter:
        prompt_bundle = None

        def create_session(self, session_id, prompt_bundle):
            self.prompt_bundle = prompt_bundle
            return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.IDLE)

    adapter = CapturingAdapter()
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_adapter=adapter))
    client.post("/skill-packs", json={"id": "memo", "title": "Memo", "description": ""})
    client.put("/skill-packs/memo/artifacts", json={
        "path": "SKILL.md",
        "content": "---\nname: memo\ndescription: Use for memos.\n---\n\n# Published Memo\n",
        "summary": "Initial memo skill",
    })
    version = client.post("/skill-packs/memo/publish", json={"publish_note": "Memo v1"}).json()
    client.put("/skill-packs/memo/artifacts", json={
        "path": "SKILL.md",
        "content": "---\nname: memo\ndescription: Draft changed.\n---\n\n# Draft Memo\n",
        "summary": "Draft-only edit",
    })

    task = client.post("/tasks", json={
        "doc_type_id": "memo",
        "pack_version_id": version["id"],
        "brief": "Write a memo",
    }).json()
    session_response = client.post(f"/tasks/{task['id']}/sessions")

    assert session_response.status_code == 200
    assert adapter.prompt_bundle is not None
    skill_path = adapter.prompt_bundle.metadata["skill_path"]
    assert adapter.prompt_bundle.metadata["pack_version_id"] == version["id"]
    assert "published" in skill_path
    assert "v001" in skill_path
    assert "draft" not in skill_path


def test_task_creation_keeps_legacy_doc_type_fallback(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "doc-types" / "legacy").mkdir(parents=True)
    (repo / "doc-types" / "legacy" / "SKILL.md").write_text(
        "# Legacy\n",
        encoding="utf-8",
    )
    (repo / "agent" / "system-prompts").mkdir(parents=True)
    (repo / "agent" / "system-prompts" / "docagent-core.md").write_text("Core prompt\n", encoding="utf-8")
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=repo))

    response = client.post("/tasks", json={"doc_type_id": "legacy", "brief": "Use legacy pack"})

    assert response.status_code == 200
    assert response.json()["pack_version_id"] is None
