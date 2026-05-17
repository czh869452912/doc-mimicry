from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from docagent_api.app import create_app
from docagent_api.db import SkillCreatorSessionRow
from docagent_api.state import DocAgentState
from docagent_contracts import PromptBundle, RuntimeOperationResult, RuntimeSessionState


def _pack_with_resource(client: TestClient) -> None:
    client.post("/skill-packs", json={"id": "memo", "title": "Memo", "description": "Memo pack"})
    client.post("/skill-packs/memo/resources/text", json={
        "group": "examples",
        "name": "memo-example.txt",
        "content": "A useful memo starts with decision context, recommendation, and risk.",
    })


def test_skill_creator_generate_writes_artifacts_and_events(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))
    _pack_with_resource(client)

    session = client.post("/skill-packs/memo/skill-creator/sessions", json={
        "message": "Generate a memo skill from the uploaded material."
    }).json()
    assert session["session_scope"] == "pack-management"

    result = client.post(f"/skill-packs/memo/skill-creator/sessions/{session['id']}/generate", json={
        "message": "Generate the initial skill pack."
    })
    assert result.status_code == 200
    assert "SKILL.md" in result.json()["paths"]

    skill = client.get("/skill-packs/memo/artifacts", params={"path": "SKILL.md"}).json()
    assert "memo" in skill["content"].lower()

    events = client.get(f"/skill-packs/memo/skill-creator/sessions/{session['id']}/events").json()
    assert any(event["event_type"] == "file/write" for event in events)


def test_skill_creator_revision_reads_manual_edit(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))
    _pack_with_resource(client)
    session = client.post("/skill-packs/memo/skill-creator/sessions", json={"message": "Start"}).json()
    client.put("/skill-packs/memo/artifacts", json={
        "path": "SKILL.md",
        "content": "---\nname: memo\ndescription: Use for executive memos.\n---\n\n# Executive Memo\n\nPreserve this line.\n",
        "summary": "Manual edit",
    })

    response = client.post(f"/skill-packs/memo/skill-creator/sessions/{session['id']}/messages", json={
        "message": "Make the checklist stricter without removing my manual line."
    })

    assert response.status_code == 200
    skill = client.get("/skill-packs/memo/artifacts", params={"path": "SKILL.md"}).json()
    assert "Preserve this line." in skill["content"]
    events = client.get(f"/skill-packs/memo/skill-creator/sessions/{session['id']}/events").json()
    event_types = [event["event_type"] for event in events]
    assert "file/read" in event_types
    assert event_types.index("file/read") < event_types.index("file/write")


class FailingCreateAdapter:
    def create_session(self, session_id, prompt_bundle):
        raise RuntimeError("runtime unavailable")


class CapturingSkillCreatorAdapter:
    def __init__(self) -> None:
        self.bundle: PromptBundle | None = None

    def create_session(self, session_id: str, prompt_bundle: PromptBundle) -> RuntimeOperationResult:
        self.bundle = prompt_bundle
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.IDLE)

    def send_prompt(
        self,
        session_id: str,
        prompt: str,
        metadata: dict[str, Any] | None = None,
    ) -> RuntimeOperationResult:
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.IDLE)

    def cancel(self, session_id: str) -> RuntimeOperationResult:
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.CANCELLED)


def test_skill_creator_prompt_includes_converted_resource_markdown_and_warnings(tmp_path: Path) -> None:
    adapter = CapturingSkillCreatorAdapter()
    client = TestClient(create_app(
        state_root=tmp_path / "state",
        repo_root=Path("."),
        runtime_adapter=adapter,
    ))
    assert client.post("/skill-packs", json={"id": "memo", "title": "Memo"}).status_code == 200
    assert client.post(
        "/skill-packs/memo/resources/text",
        json={
            "group": "examples",
            "name": "board-memo.txt",
            "content": "Executive summary first. Élan 中文. Then decision context. Then risks.",
        },
    ).status_code == 200

    response = client.post(
        "/skill-packs/memo/skill-creator/sessions",
        json={"message": "Generate the memo skill"},
    )

    assert response.status_code == 200
    assert adapter.bundle is not None
    assert "Executive summary first" in adapter.bundle.task_instruction
    assert "Élan 中文" in adapter.bundle.task_instruction
    assert "resources/markdown/examples/board-memo.md" in adapter.bundle.task_instruction
    assert "warnings" in adapter.bundle.task_instruction


def test_skill_creator_session_create_failure_removes_session(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    client = TestClient(create_app(
        state_root=state_root,
        repo_root=Path("."),
        runtime_adapter=FailingCreateAdapter(),
    ))
    _pack_with_resource(client)

    response = client.post("/skill-packs/memo/skill-creator/sessions", json={"message": "Start"})

    assert response.status_code == 502
    assert response.json()["detail"] == "Skill Creator runtime session creation failed: runtime unavailable"
    state = DocAgentState(state_root)
    with state._Session() as db:
        assert db.query(SkillCreatorSessionRow).count() == 0
