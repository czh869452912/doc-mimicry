import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

import docagent_api.app as app_module
from docagent_api.app import create_app
from docagent_api.state import DocAgentState
from docagent_contracts import PromptBundle, RuntimeOperationResult, RuntimeSessionState


def test_invalid_outline_approval_returns_409(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build onboarding analytics"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    response = client.post(
        f"/sessions/{session['id']}/outline/approve",
        json={"outline_markdown": "# Outline\n"},
    )

    assert response.status_code == 409
    assert "Cannot transition session" in response.json()["detail"]


def test_cancel_running_session_returns_cancelled(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build onboarding analytics"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    client.post(f"/sessions/{session['id']}/loop/start")

    response = client.post(f"/sessions/{session['id']}/cancel")

    assert response.status_code == 200
    assert response.json()["next_state"] == "cancelled"
    assert client.get(f"/sessions/{session['id']}").json()["status"] == "cancelled"


class FailingSendAdapter:
    def create_session(self, session_id: str, prompt_bundle: PromptBundle) -> RuntimeOperationResult:
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.IDLE)

    def send_message(self, session_id: str, message: str) -> RuntimeOperationResult:
        raise RuntimeError("runtime session is not available")

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


def test_runtime_error_rolls_session_back_to_previous_state(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(app_module, "create_runtime_adapter", lambda runtime_name=None: FailingSendAdapter())
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="openhands"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build onboarding analytics"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    response = client.post(f"/sessions/{session['id']}/messages", json={"message": "hello"})

    assert response.status_code == 502
    assert response.json()["detail"] == "Runtime operation failed: runtime session is not available"
    assert client.get(f"/sessions/{session['id']}").json()["status"] == "idle"
    assert client.post(f"/sessions/{session['id']}/loop/start").status_code == 200


class FailingStreamAdapter:
    def create_session(self, session_id: str, prompt_bundle: PromptBundle) -> RuntimeOperationResult:
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.IDLE)

    def start_loop_stream(self, session_id: str, sink: Any) -> None:
        raise RuntimeError("runtime unavailable")

    def cancel(self, session_id: str) -> RuntimeOperationResult:
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.CANCELLED)

    def get_state(self, session_id: str) -> RuntimeSessionState:
        return RuntimeSessionState.IDLE


def test_background_runtime_failure_appends_error_kind_event(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(app_module, "create_runtime_adapter", lambda runtime_name=None: FailingStreamAdapter())
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="openhands"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    client.post(f"/sessions/{session['id']}/loop/start?background=true")

    deadline = time.monotonic() + 5.0
    events = []
    while time.monotonic() < deadline:
        events = client.get(f"/sessions/{session['id']}/timeline").json()
        if any(e["kind"] in ("error", "user_message") and "failed" in e.get("summary", "").lower() for e in events):
            break
        time.sleep(0.05)
    user_message_failures = [e for e in events if e["kind"] == "user_message" and "failed" in e.get("summary", "").lower()]
    assert user_message_failures == [], f"failure must not be user_message kind: {user_message_failures}"
    error_events = [e for e in events if e["kind"] == "error"]
    assert len(error_events) == 1
    assert "runtime unavailable" in error_events[0]["summary"]
    assert error_events[0]["status"] == "failed"


def test_cancel_completed_session_returns_409(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    client = TestClient(create_app(state_root=state_root, repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session_resp = client.post(f"/tasks/{task['id']}/sessions").json()
    db = DocAgentState(state_root)
    s = db.get_session(session_resp["id"])
    s["status"] = "completed"
    db.save_session(s)

    response = client.post(f"/sessions/{session_resp['id']}/cancel")

    assert response.status_code == 409


def test_startup_logs_warning_for_interrupted_running_sessions(tmp_path: Path) -> None:
    """With Celery-backed state, startup no longer force-fails running sessions.
    It only logs a warning; Celery handles recovery. Status stays unchanged."""
    state_root = tmp_path / "state"
    client = TestClient(create_app(state_root=state_root, repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build onboarding analytics"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    state = DocAgentState(state_root)
    session["status"] = "running_revision"
    state.save_session(session)

    # Re-create the app — now only warns, does not force-fail sessions
    recovered_client = TestClient(create_app(state_root=state_root, repo_root=Path("."), runtime_name="mock"))

    assert recovered_client.get(f"/sessions/{session['id']}").json()["status"] == "running_revision"
    new_session = recovered_client.post(f"/tasks/{task['id']}/sessions").json()
    assert recovered_client.post(f"/sessions/{new_session['id']}/loop/start").status_code == 200


def test_send_message_background_uses_running_chat_state(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    client.post(f"/sessions/{session['id']}/loop/start")
    client.post(f"/sessions/{session['id']}/outline/approve", json={"outline_markdown": "# Outline\n"})

    response = client.post(
        f"/sessions/{session['id']}/messages?background=true",
        json={"message": "hello"},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "running_chat"
