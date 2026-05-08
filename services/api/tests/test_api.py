from pathlib import Path
import os
from threading import Event
import time
from typing import Any

from fastapi.testclient import TestClient

from docagent_api.app import create_app
from docagent_api.app import state_root_from_env
from docagent_contracts import (
    PromptBundle,
    RawRuntimeEvent,
    RuntimeEventSink,
    RuntimeKind,
    RuntimeOperationResult,
    RuntimeSessionState,
)


class StreamingFakeAdapter:
    def __init__(self) -> None:
        self.first_event_sent = Event()
        self.finish = Event()

    def create_session(self, session_id: str, prompt_bundle: PromptBundle) -> RuntimeOperationResult:
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.IDLE)

    def send_message(self, session_id: str, message: str) -> RuntimeOperationResult:
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.DRAFT_READY)

    def send_message_stream(
        self,
        session_id: str,
        message: str,
        sink: RuntimeEventSink,
    ) -> RuntimeOperationResult:
        sink(_raw(session_id, "stream-1", {"kind": "file_written", "path": "draft/draft.md"}))
        self.first_event_sent.set()
        assert self.finish.wait(timeout=2)
        sink(_raw(session_id, "stream-2", {"kind": "file_written", "path": "draft/final.md"}))
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.DRAFT_READY)

    def start_loop(self, session_id: str) -> RuntimeOperationResult:
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.AWAIT_OUTLINE_APPROVAL)

    def approve_outline(self, session_id: str) -> RuntimeOperationResult:
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.DRAFT_READY)

    def revise_selection(self, session_id: str, selection: str, instruction: str) -> RuntimeOperationResult:
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.DRAFT_READY)

    def run_checklist(self, session_id: str) -> RuntimeOperationResult:
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.DRAFT_READY)

    def export_markdown(self, session_id: str) -> RuntimeOperationResult:
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.COMPLETED)

    def cancel(self, session_id: str) -> RuntimeOperationResult:
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.CANCELLED)

    def get_state(self, session_id: str) -> RuntimeSessionState:
        return RuntimeSessionState.IDLE


def _raw(session_id: str, raw_id: str, payload: dict[str, Any]) -> RawRuntimeEvent:
    return RawRuntimeEvent(
        id=raw_id,
        session_id=session_id,
        runtime=RuntimeKind.OPENHANDS,
        runtime_session_id="runtime-001",
        kind=str(payload.get("kind", "event")),
        payload=payload,
        created_at="2026-05-07T00:00:00Z",
    )


def test_health_endpoint(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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

    message_response = client.post(
        f"/sessions/{session['id']}/messages",
        json={"message": "Start the PRD"},
    )
    assert message_response.status_code == 200
    assert message_response.json()["event_count"] == 6

    timeline = client.get(f"/sessions/{session['id']}/timeline").json()
    assert [event["kind"] for event in timeline] == [
        "user_message",
        "read_skill",
        "extract_style",
        "extract_structure",
        "generate_outline",
        "update_draft",
    ]

    draft = client.get(f"/tasks/{task['id']}/draft").json()
    assert "# PRD Draft" in draft["markdown"]

    update_response = client.put(f"/tasks/{task['id']}/draft", json={"markdown": "# Edited\n"})
    assert update_response.status_code == 200
    assert client.get(f"/tasks/{task['id']}/draft").json()["markdown"] == "# Edited\n"


def test_background_message_streams_partial_timeline_before_completion(tmp_path: Path) -> None:
    adapter = StreamingFakeAdapter()
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_adapter=adapter))

    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build billing controls"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

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
    assert "update_draft" in kinds
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
