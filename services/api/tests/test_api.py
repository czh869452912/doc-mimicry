from pathlib import Path
import os
from threading import Event
import time
from typing import Any

from fastapi.testclient import TestClient

from docagent_api.app import create_app
from docagent_api.app import state_root_from_env
from docagent_api.request_models import PromptRequest
from docagent_api.state import DocAgentState
from docagent_contracts import (
    PromptBundle,
    RuntimeOperationResult,
    RuntimeSessionState,
)


class StreamingFakeAdapter:
    def __init__(self) -> None:
        self.first_event_sent = Event()
        self.finish = Event()

    def create_session(self, session_id: str, prompt_bundle: PromptBundle) -> RuntimeOperationResult:
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.IDLE)

    def send_prompt(
        self,
        session_id: str,
        prompt: str,
        metadata: dict[str, object] | None = None,
    ) -> RuntimeOperationResult:
        action = (metadata or {}).get("action")
        if action == "start_loop":
            return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.AWAIT_OUTLINE_APPROVAL)
        if action == "approve_outline":
            return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.DRAFT_READY)
        self.first_event_sent.set()
        assert self.finish.wait(timeout=2)
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.DRAFT_READY)

    def cancel(self, session_id: str) -> RuntimeOperationResult:
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.CANCELLED)

    def get_state(self, session_id: str) -> RuntimeSessionState:
        return RuntimeSessionState.IDLE


def test_health_endpoint(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "runtime": "mock-acp"}


def test_prompt_request_metadata_default_is_not_shared() -> None:
    first = PromptRequest(prompt="one")
    second = PromptRequest(prompt="two")

    first.metadata["action"] = "send_message"

    assert second.metadata == {}


def test_create_app_uses_state_root_from_environment(tmp_path: Path, monkeypatch) -> None:
    state_root = tmp_path / "env-state"
    monkeypatch.setenv("DOCAGENT_STATE_ROOT", str(state_root))
    client = TestClient(create_app(repo_root=Path(".")))

    response = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Env state root"})

    assert response.status_code == 200
    assert state_root.exists()
    assert Path(response.json()["workspace_root"]).is_relative_to(state_root)


def test_doc_type_endpoints(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))

    listing = client.get("/doc-types")
    detail = client.get("/doc-types/prd")

    assert listing.status_code == 200
    assert listing.json()[0]["id"] == "prd"
    assert detail.status_code == 200
    assert detail.json()["id"] == "prd"
    assert "skill_markdown" in detail.json()


def test_task_session_message_timeline_and_draft_roundtrip(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))

    task_response = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build billing controls"})
    assert task_response.status_code == 200
    task = task_response.json()

    session_response = client.post(f"/tasks/{task['id']}/sessions")
    assert session_response.status_code == 200
    session = session_response.json()

    # Reach draft_ready via the proper workflow before sending a chat message
    assert client.post(f"/sessions/{session['id']}/loop/start").status_code == 200
    assert client.post(
        f"/sessions/{session['id']}/outline/approve",
        json={"outline_markdown": "# Outline\n"},
    ).status_code == 200

    message_response = client.post(
        f"/sessions/{session['id']}/messages",
        json={"message": "Revise the draft"},
    )
    assert message_response.status_code == 200
    # Revise path returns 3 events (user_message, create_checkpoint, update_draft)
    assert message_response.json()["event_count"] == 3

    timeline = client.get(f"/sessions/{session['id']}/timeline").json()
    timeline_kinds = [event["kind"] for event in timeline]
    assert "user_message" in timeline_kinds
    assert "update_draft" in timeline_kinds

    draft = client.get(f"/tasks/{task['id']}/draft").json()
    assert "# PRD Draft" in draft["markdown"]

    update_response = client.put(f"/tasks/{task['id']}/draft", json={"markdown": "# Edited\n"})
    assert update_response.status_code == 200
    assert client.get(f"/tasks/{task['id']}/draft").json()["markdown"] == "# Edited\n"


def test_draft_update_is_blocked_while_session_running_unless_forced(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build onboarding analytics"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    db = DocAgentState(tmp_path / "state")
    session["status"] = "running_chat"
    db.save_session(session)

    blocked = client.put(f"/tasks/{task['id']}/draft", json={"markdown": "# Edited\n"})
    assert blocked.status_code == 409

    forced = client.put(f"/tasks/{task['id']}/draft", json={"markdown": "# Edited\n", "force": True})
    assert forced.status_code == 200
    assert forced.json()["markdown"] == "# Edited\n"


def test_background_message_records_user_message_while_chat_is_running(tmp_path: Path) -> None:
    adapter = StreamingFakeAdapter()
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_adapter=adapter))

    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build billing controls"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    # Reach draft_ready before sending a message (the ACP prompt action requires a draft)
    assert client.post(f"/sessions/{session['id']}/loop/start").status_code == 200
    assert client.post(
        f"/sessions/{session['id']}/outline/approve",
        json={"outline_markdown": "# Outline\n"},
    ).status_code == 200

    response = client.post(
        f"/sessions/{session['id']}/messages?background=true",
        json={"message": "Start the PRD"},
    )

    assert response.status_code == 202
    assert response.json()["accepted"] is True
    assert adapter.first_event_sent.wait(timeout=2)

    timeline = client.get(f"/sessions/{session['id']}/timeline").json()
    kinds = [event["kind"] for event in timeline]
    assert "user_message" in kinds
    assert client.get(f"/sessions/{session['id']}").json()["status"] == "running_chat"

    adapter.finish.set()
    deadline = time.time() + 2
    while time.time() < deadline:
        if client.get(f"/sessions/{session['id']}").json()["status"] == "draft_ready":
            break
        time.sleep(0.05)

    assert client.get(f"/sessions/{session['id']}").json()["status"] == "draft_ready"


def test_task_creation_keeps_title_separate_from_description(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))

    response = client.post(
        "/tasks",
        json={
            "doc_type_id": "prd",
            "title": "Billing controls PRD",
            "description": "Write a PRD for enterprise billing controls.",
        },
    )

    assert response.status_code == 200
    task = response.json()
    assert task["title"] == "Billing controls PRD"
    assert task["description"] == "Write a PRD for enterprise billing controls."
    assert task["brief"] == "Write a PRD for enterprise billing controls."


def test_task_without_explicit_title_gets_title_from_description(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))

    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build a search feature"}).json()
    fetched = client.get(f"/tasks/{task['id']}").json()

    assert fetched["title"] == "Build a search feature"
    assert fetched["description"] == "Build a search feature"


def test_all_route_prefixes_respond_after_refactor(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))
    assert client.get("/health").status_code == 200
    assert client.get("/doc-types").status_code == 200
    assert client.get("/tasks").status_code == 200


def test_openapi_schema_includes_task_response_fields(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))
    schema = client.get("/openapi.json").json()

    task_schema = schema["components"]["schemas"]["TaskResponse"]
    assert "title" in task_schema["properties"]
    assert "doc_type_id" in task_schema["properties"]


def test_state_root_can_be_read_from_environment(tmp_path: Path) -> None:
    state_root = tmp_path / "custom-state"
    original = os.environ.get("DOCAGENT_STATE_ROOT")
    os.environ["DOCAGENT_STATE_ROOT"] = str(state_root)
    try:
        assert state_root_from_env() == state_root
    finally:
        if original is None:
            os.environ.pop("DOCAGENT_STATE_ROOT", None)
        else:
            os.environ["DOCAGENT_STATE_ROOT"] = original
