import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import docagent_api.app as app_module
from docagent_api.app import create_app
from docagent_api.state import DocAgentState
from docagent_contracts import AcpRuntimeUpdate, PromptBundle, RuntimeOperationResult, RuntimeSessionState


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


def test_cancel_running_session_releases_operation_lease(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    client = TestClient(create_app(state_root=state_root, repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build onboarding analytics"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    db = DocAgentState(state_root)
    assert db.acquire_operation_lease(session["id"], "celery-001") is True
    session["status"] = "running_chat"
    db.save_session(session)

    response = client.post(f"/sessions/{session['id']}/cancel")

    assert response.status_code == 200
    assert "celery_task_id" not in DocAgentState(state_root).get_session(session["id"])


def test_startup_recovery_error_is_mirrored_to_acp_events(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    client = TestClient(create_app(state_root=state_root, repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Recover me"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    state = DocAgentState(state_root)
    row = state.get_session(session["id"])
    row["status"] = "running_chat"
    state.save_session(row)

    recovered = TestClient(create_app(state_root=state_root, repo_root=Path("."), runtime_name="mock"))

    assert recovered.get(f"/sessions/{session['id']}").json()["status"] == "failed"
    acp_events = recovered.get(f"/sessions/{session['id']}/events").json()
    assert any(
        event["event_type"] == "docagent/projection"
        and event["projection"]["timeline_kind"] == "error"
        and "interrupted" in event["projection"]["summary"].lower()
        for event in acp_events
    )


class FailingSendAdapter:
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
        if action == "run_checklist":
            return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.DRAFT_READY)
        raise RuntimeError("runtime session is not available")

    def cancel(self, session_id: str) -> RuntimeOperationResult:
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.CANCELLED)

    def get_state(self, session_id: str) -> RuntimeSessionState:
        return RuntimeSessionState.IDLE


class AcpUpdateAdapter(FailingSendAdapter):
    def send_prompt(
        self,
        session_id: str,
        prompt: str,
        metadata: dict[str, object] | None = None,
    ) -> RuntimeOperationResult:
        return RuntimeOperationResult(
            session_id=session_id,
            next_state=RuntimeSessionState.DRAFT_READY,
            acp_updates=[
                AcpRuntimeUpdate(
                    session_id=session_id,
                    event_type="message_delta",
                    payload={"role": "assistant", "content": "streamed", "message_id": "m1"},
                )
            ],
        )


class ConflictingEventTypeAdapter(FailingSendAdapter):
    def send_prompt(
        self,
        session_id: str,
        prompt: str,
        metadata: dict[str, object] | None = None,
    ) -> RuntimeOperationResult:
        return RuntimeOperationResult(
            session_id=session_id,
            next_state=RuntimeSessionState.DRAFT_READY,
            acp_updates=[
                AcpRuntimeUpdate(
                    session_id=session_id,
                    event_type="tool/result",
                    payload={"event_type": "message_delta", "content": "done"},
                )
            ],
        )


class PermissionAnswerAdapter(FailingSendAdapter):
    def __init__(self) -> None:
        self.answers: list[tuple[str, str, str]] = []

    def answer_permission(
        self,
        session_id: str,
        request_id: str,
        decision: str,
    ) -> RuntimeOperationResult:
        self.answers.append((session_id, request_id, decision))
        return RuntimeOperationResult(
            session_id=session_id,
            next_state=RuntimeSessionState.IDLE,
            acp_updates=[
                AcpRuntimeUpdate(
                    session_id=session_id,
                    event_type="permission/resolved",
                    payload={"request_id": request_id, "decision": decision},
                )
            ],
        )


class PromptOnlyAdapter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def create_session(self, session_id: str, prompt_bundle: PromptBundle) -> RuntimeOperationResult:
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.IDLE)

    def send_prompt(
        self,
        session_id: str,
        prompt: str,
        metadata: dict[str, object] | None = None,
    ) -> RuntimeOperationResult:
        prompt_metadata = metadata or {}
        self.calls.append((prompt, prompt_metadata))
        action = prompt_metadata.get("action")
        next_state = {
            "start_loop": RuntimeSessionState.AWAIT_OUTLINE_APPROVAL,
            "send_message": RuntimeSessionState.DRAFT_READY,
        }.get(action, RuntimeSessionState.DRAFT_READY)
        return RuntimeOperationResult(session_id=session_id, next_state=next_state)

    def cancel(self, session_id: str) -> RuntimeOperationResult:
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.CANCELLED)

    def get_state(self, session_id: str) -> RuntimeSessionState:
        return RuntimeSessionState.IDLE


class LegacyOnlyDocumentActionAdapter(FailingSendAdapter):
    send_prompt = None

    def start_loop(self, session_id: str) -> RuntimeOperationResult:
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.AWAIT_OUTLINE_APPROVAL)


class FailingCreateAdapter(FailingSendAdapter):
    def create_session(self, session_id: str, prompt_bundle: PromptBundle) -> RuntimeOperationResult:
        raise RuntimeError("OpenHands Agent Server is unreachable")


def test_create_session_runtime_failure_returns_502_and_deletes_session(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(app_module, "create_runtime_adapter", lambda runtime_name=None: FailingCreateAdapter())
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="openhands"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build onboarding analytics"}).json()

    response = client.post(f"/tasks/{task['id']}/sessions")

    assert response.status_code == 502
    assert response.json()["detail"] == "Runtime session creation failed: OpenHands Agent Server is unreachable"
    assert client.get(f"/tasks/{task['id']}/sessions").json() == []


def test_create_task_rejects_malicious_doc_type_id(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))

    response = client.post("/tasks", json={"doc_type_id": "%2e%2e%2fprd", "brief": "test"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Document type not found"


def test_create_app_reads_repo_root_from_env(tmp_path: Path, monkeypatch: Any) -> None:
    repo = tmp_path / "repo"
    (repo / "agent" / "system-prompts").mkdir(parents=True)
    (repo / "doc-types" / "custom").mkdir(parents=True)
    (repo / "agent" / "system-prompts" / "docagent-core.md").write_text("Core prompt", encoding="utf-8")
    (repo / "doc-types" / "custom" / "SKILL.md").write_text("# Custom Skill", encoding="utf-8")
    monkeypatch.setenv("DOCAGENT_REPO_ROOT", str(repo))

    client = TestClient(create_app(state_root=tmp_path / "state", runtime_name="mock"))

    response = client.post("/tasks", json={"doc_type_id": "custom", "brief": "test"})

    assert response.status_code == 200
    assert response.json()["doc_type_id"] == "custom"


def test_runtime_error_rolls_session_back_to_previous_state(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(app_module, "create_runtime_adapter", lambda runtime_name=None: FailingSendAdapter())
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="openhands"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build onboarding analytics"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    # Reach draft_ready before sending a message (FailingSendAdapter supports this workflow)
    assert client.post(f"/sessions/{session['id']}/loop/start").status_code == 200
    assert client.post(
        f"/sessions/{session['id']}/outline/approve",
        json={"outline_markdown": "# Outline\n"},
    ).status_code == 200

    response = client.post(f"/sessions/{session['id']}/messages", json={"message": "hello"})

    assert response.status_code == 502
    assert response.json()["detail"] == "Runtime operation failed: runtime session is not available"
    # Session must roll back to draft_ready (the state before the failed send_message)
    assert client.get(f"/sessions/{session['id']}").json()["status"] == "draft_ready"
    # Confirm the session is still usable from draft_ready
    assert client.post(f"/sessions/{session['id']}/checklist/run").status_code == 200


class FailingStreamAdapter:
    def create_session(self, session_id: str, prompt_bundle: PromptBundle) -> RuntimeOperationResult:
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.IDLE)

    def send_prompt(
        self,
        session_id: str,
        prompt: str,
        metadata: dict[str, object] | None = None,
    ) -> RuntimeOperationResult:
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


def test_background_runtime_failure_appends_acp_error_event(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(app_module, "create_runtime_adapter", lambda runtime_name=None: FailingStreamAdapter())
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="openhands"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    client.post(f"/sessions/{session['id']}/loop/start?background=true")

    deadline = time.monotonic() + 5.0
    acp_events = []
    while time.monotonic() < deadline:
        acp_events = client.get(f"/sessions/{session['id']}/events").json()
        if any(event["event_type"] == "runtime/error" for event in acp_events):
            break
        time.sleep(0.05)

    errors = [event for event in acp_events if event["event_type"] == "runtime/error"]
    assert len(errors) == 1
    assert "runtime unavailable" in errors[0]["payload"]["message"]


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


def test_startup_marks_interrupted_running_sessions_failed(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    client = TestClient(create_app(state_root=state_root, repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build onboarding analytics"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    state = DocAgentState(state_root)
    session["status"] = "running_revision"
    state.save_session(session)

    recovered_client = TestClient(create_app(state_root=state_root, repo_root=Path("."), runtime_name="mock"))

    assert recovered_client.get(f"/sessions/{session['id']}").json()["status"] == "failed"
    events = recovered_client.get(f"/sessions/{session['id']}/timeline").json()
    assert any(event["kind"] == "error" and "interrupted" in event["summary"].lower() for event in events)
    new_session = recovered_client.post(f"/tasks/{task['id']}/sessions").json()
    assert recovered_client.post(f"/sessions/{new_session['id']}/loop/start").status_code == 200


def test_cancel_revoke_persisted_celery_task(tmp_path: Path, monkeypatch: Any) -> None:
    revoked: list[str] = []

    class FakeControl:
        @staticmethod
        def revoke(task_id: str, terminate: bool = False) -> None:
            revoked.append(f"{task_id}:{terminate}")

    monkeypatch.setattr("docagent_api.routes.sessions.celery_app.control", FakeControl())
    state_root = tmp_path / "state"
    client = TestClient(create_app(state_root=state_root, repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    db = DocAgentState(state_root)
    assert db.acquire_operation_lease(session["id"], "celery-001") is True
    session["status"] = "running_chat"
    db.save_session(session)

    response = client.post(f"/sessions/{session['id']}/cancel")

    assert response.status_code == 200
    assert revoked == ["celery-001:True"]


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


def test_prompt_endpoint_runs_chat_and_records_acp_prompt_and_projection_events(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    client.post(f"/sessions/{session['id']}/loop/start")
    client.post(f"/sessions/{session['id']}/outline/approve", json={"outline_markdown": "# Outline\n"})

    response = client.post(
        f"/sessions/{session['id']}/prompt",
        json={"prompt": "Please revise the draft", "metadata": {"action": "send_message"}},
    )

    assert response.status_code == 200
    assert response.json()["next_state"] == "draft_ready"
    acp_events = client.get(f"/sessions/{session['id']}/events").json()
    assert any(
        event["event_type"] == "docagent/prompt"
        and event["payload"]["prompt"] == "Please revise the draft"
        and event["payload"]["metadata"]["action"] == "send_message"
        for event in acp_events
    )
    assert any(
        event["event_type"] == "docagent/projection"
        and event["projection"]["timeline_kind"] == "update_draft"
        for event in acp_events
    )


def test_product_action_endpoint_prefers_acp_prompt_runtime_method(tmp_path: Path) -> None:
    adapter = PromptOnlyAdapter()
    client = TestClient(create_app(
        state_root=tmp_path / "state",
        repo_root=Path("."),
        runtime_adapter=adapter,
    ))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    response = client.post(f"/sessions/{session['id']}/loop/start")

    assert response.status_code == 200
    assert response.json()["next_state"] == "await_outline_approval"
    assert adapter.calls == [
        (
            "Build context files and propose an outline. Stop when outline approval is required.",
            {"action": "start_loop"},
        )
    ]


def test_product_action_endpoint_rejects_adapter_without_acp_prompt_method(tmp_path: Path) -> None:
    client = TestClient(create_app(
        state_root=tmp_path / "state",
        repo_root=Path("."),
        runtime_adapter=LegacyOnlyDocumentActionAdapter(),
    ))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    response = client.post(f"/sessions/{session['id']}/loop/start")

    assert response.status_code == 502
    assert response.json()["detail"] == "Runtime operation failed: Runtime adapter must implement send_prompt"
    assert client.get(f"/sessions/{session['id']}").json()["status"] == "idle"


@pytest.mark.parametrize(
    ("endpoint", "json_body", "initial_state"),
    [
        ("/messages", {"message": "hello"}, "draft_ready"),
        ("/outline/approve", {"outline_markdown": "# Outline\n"}, "await_outline_approval"),
        (
            "/revision/selection",
            {"selected_text": "Define the desired product outcome.", "instruction": "Make it sharper"},
            "draft_ready",
        ),
        ("/checklist/run", None, "draft_ready"),
        ("/artifacts/export-markdown", None, "draft_ready"),
    ],
)
def test_sync_product_actions_reject_adapter_without_acp_prompt_method(
    tmp_path: Path,
    endpoint: str,
    json_body: dict[str, str] | None,
    initial_state: str,
) -> None:
    client = TestClient(create_app(
        state_root=tmp_path / "state",
        repo_root=Path("."),
        runtime_adapter=LegacyOnlyDocumentActionAdapter(),
    ))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    session["status"] = initial_state
    DocAgentState(tmp_path / "state").save_session(session)

    response = client.post(f"/sessions/{session['id']}{endpoint}", json=json_body)

    assert response.status_code == 502
    assert response.json()["detail"] == "Runtime operation failed: Runtime adapter must implement send_prompt"
    assert client.get(f"/sessions/{session['id']}").json()["status"] == initial_state


@pytest.mark.parametrize(
    ("endpoint", "json_body", "expected_state"),
    [
        ("/messages?background=true", {"message": "hello"}, "draft_ready"),
        ("/outline/approve?background=true", {"outline_markdown": "# Outline\n"}, "await_outline_approval"),
        (
            "/revision/selection?background=true",
            {"selected_text": "Define the desired product outcome.", "instruction": "Make it sharper"},
            "draft_ready",
        ),
        ("/checklist/run?background=true", None, "draft_ready"),
        ("/artifacts/export-markdown?background=true", None, "draft_ready"),
    ],
)
def test_background_product_actions_reject_adapter_without_acp_prompt_method(
    tmp_path: Path,
    endpoint: str,
    json_body: dict[str, str] | None,
    expected_state: str,
) -> None:
    client = TestClient(create_app(
        state_root=tmp_path / "state",
        repo_root=Path("."),
        runtime_adapter=LegacyOnlyDocumentActionAdapter(),
    ))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    db = DocAgentState(tmp_path / "state")
    session["status"] = expected_state
    db.save_session(session)

    response = client.post(f"/sessions/{session['id']}{endpoint}", json=json_body)

    assert response.status_code == 502
    assert response.json()["detail"] == "Runtime operation failed: Runtime adapter must implement send_prompt"
    assert client.get(f"/sessions/{session['id']}").json()["status"] == expected_state


def test_background_message_rejects_missing_acp_prompt_without_orphan_user_timeline(tmp_path: Path) -> None:
    client = TestClient(create_app(
        state_root=tmp_path / "state",
        repo_root=Path("."),
        runtime_adapter=LegacyOnlyDocumentActionAdapter(),
    ))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    session["status"] = "draft_ready"
    DocAgentState(tmp_path / "state").save_session(session)

    response = client.post(
        f"/sessions/{session['id']}/messages?background=true",
        json={"message": "hello"},
    )

    assert response.status_code == 502
    timeline_events = client.get(f"/sessions/{session['id']}/timeline").json()
    assert all(event["kind"] != "user_message" for event in timeline_events)


def test_background_revise_selection_rejects_missing_acp_prompt_without_running_state_transition(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(
        state_root=tmp_path / "state",
        repo_root=Path("."),
        runtime_adapter=LegacyOnlyDocumentActionAdapter(),
    ))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    session["status"] = "draft_ready"
    DocAgentState(tmp_path / "state").save_session(session)

    response = client.post(
        f"/sessions/{session['id']}/revision/selection?background=true",
        json={"selected_text": "Example text", "instruction": "Make it sharper"},
    )

    assert response.status_code == 502
    timeline_events = client.get(f"/sessions/{session['id']}/timeline").json()
    assert all(
        event["kind"] != "session_status" or "running_revision" not in event["summary"]
        for event in timeline_events
    )


def test_background_revise_selection_passes_complete_acp_prompt_metadata(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setenv("DOCAGENT_QUEUE", "celery")
    delayed_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    class FakeTask:
        @staticmethod
        def delay(*args: Any, **kwargs: Any) -> None:
            delayed_calls.append((args, kwargs))

    monkeypatch.setattr("docagent_api.worker_tasks.run_session", FakeTask)
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    assert client.post(f"/sessions/{session['id']}/loop/start").status_code == 200
    assert client.post(
        f"/sessions/{session['id']}/outline/approve",
        json={"outline_markdown": "# Outline\n"},
    ).status_code == 200

    response = client.post(
        f"/sessions/{session['id']}/revision/selection?background=true",
        json={
            "selected_text": "Define the desired product outcome.",
            "instruction": "Make it sharper",
        },
    )

    assert response.status_code == 202
    _, operation_name, operation_kwargs, _ = delayed_calls[0][0]
    assert operation_name == "send_prompt"
    assert operation_kwargs["metadata"] == {
        "action": "revise_selection",
        "selection": "Define the desired product outcome.",
        "instruction": "Make it sharper",
    }
    assert operation_kwargs["prompt"].endswith("Instruction:\nMake it sharper")


def test_runtime_acp_updates_are_persisted_to_event_store(tmp_path: Path) -> None:
    client = TestClient(create_app(
        state_root=tmp_path / "state",
        repo_root=Path("."),
        runtime_adapter=AcpUpdateAdapter(),
    ))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    client.post(f"/sessions/{session['id']}/loop/start")
    client.post(f"/sessions/{session['id']}/outline/approve", json={"outline_markdown": "# Outline\n"})

    response = client.post(f"/sessions/{session['id']}/prompt", json={"prompt": "hello"})

    assert response.status_code == 200
    acp_events = client.get(f"/sessions/{session['id']}/events").json()
    assert any(
        event["event_type"] == "message_delta"
        and event["payload"]["content"] == "streamed"
        for event in acp_events
    )


def test_runtime_acp_update_event_type_cannot_be_overridden_by_payload(tmp_path: Path) -> None:
    client = TestClient(create_app(
        state_root=tmp_path / "state",
        repo_root=Path("."),
        runtime_adapter=ConflictingEventTypeAdapter(),
    ))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    response = client.post(f"/sessions/{session['id']}/prompt", json={"prompt": "hello"})

    assert response.status_code == 200
    acp_events = client.get(f"/sessions/{session['id']}/events").json()
    stored = [event for event in acp_events if event["payload"].get("content") == "done"]
    assert len(stored) == 1
    assert stored[0]["event_type"] == "tool/result"
    assert stored[0]["payload"]["event_type"] == "tool/result"


def test_permission_answer_gateway_is_task_scoped_and_persists_response(tmp_path: Path) -> None:
    adapter = PermissionAnswerAdapter()
    client = TestClient(create_app(
        state_root=tmp_path / "state",
        repo_root=Path("."),
        runtime_adapter=adapter,
    ))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    response = client.post(
        f"/sessions/{session['id']}/permissions/permission-1/answer",
        json={"decision": "allow"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == session["id"]
    assert body["next_state"] == "idle"
    assert body["accepted"] is True
    assert body["status"] == "idle"
    assert adapter.answers == [(session["id"], "permission-1", "allow")]
    acp_events = client.get(f"/sessions/{session['id']}/events").json()
    assert any(
        event["event_type"] == "permission/response"
        and event["payload"]["request_id"] == "permission-1"
        and event["payload"]["decision"] == "allow"
        for event in acp_events
    )
    assert any(event["event_type"] == "permission/resolved" for event in acp_events)


def test_permission_answer_gateway_requires_session_task_to_exist(tmp_path: Path, monkeypatch: Any) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    original_get_task = DocAgentState.get_task

    def missing_task(self: DocAgentState, task_id: str):
        if task_id == task["id"]:
            return None
        return original_get_task(self, task_id)

    monkeypatch.setattr(DocAgentState, "get_task", missing_task)

    response = client.post(
        f"/sessions/{session['id']}/permissions/permission-1/answer",
        json={"decision": "deny"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_permission_answer_gateway_rejects_unknown_decision(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    response = client.post(
        f"/sessions/{session['id']}/permissions/permission-1/answer",
        json={"decision": "maybe"},
    )

    assert response.status_code == 422
    assert "allow" in str(response.json()["detail"])
    assert "deny" in str(response.json()["detail"])


def test_permission_answer_gateway_does_not_record_response_when_runtime_cannot_answer(tmp_path: Path) -> None:
    client = TestClient(create_app(
        state_root=tmp_path / "state",
        repo_root=Path("."),
        runtime_adapter=FailingSendAdapter(),
    ))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    response = client.post(
        f"/sessions/{session['id']}/permissions/permission-1/answer",
        json={"decision": "allow"},
    )

    assert response.status_code == 501
    acp_events = client.get(f"/sessions/{session['id']}/events").json()
    assert not any(event["event_type"] == "permission/response" for event in acp_events)


def test_fallback_user_message_projection_is_mirrored_to_acp_event_store(tmp_path: Path) -> None:
    client = TestClient(create_app(
        state_root=tmp_path / "state",
        repo_root=Path("."),
        runtime_adapter=AcpUpdateAdapter(),
    ))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    client.post(f"/sessions/{session['id']}/loop/start")
    client.post(f"/sessions/{session['id']}/outline/approve", json={"outline_markdown": "# Outline\n"})

    response = client.post(f"/sessions/{session['id']}/prompt", json={"prompt": "hello"})

    assert response.status_code == 200
    timeline_events = client.get(f"/sessions/{session['id']}/timeline").json()
    user_events = [event for event in timeline_events if event["kind"] == "user_message"]
    assert len(user_events) == 1
    acp_events = client.get(f"/sessions/{session['id']}/events").json()
    assert any(
        event["event_type"] == "docagent/projection"
        and event["projection"]["timeline_kind"] == "user_message"
        and event["projection"]["timeline_id"] == user_events[0]["id"]
        for event in acp_events
    )


def test_message_endpoint_is_thin_wrapper_over_prompt_action(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    client.post(f"/sessions/{session['id']}/loop/start")
    client.post(f"/sessions/{session['id']}/outline/approve", json={"outline_markdown": "# Outline\n"})

    response = client.post(f"/sessions/{session['id']}/messages", json={"message": "hello"})

    assert response.status_code == 200
    acp_events = client.get(f"/sessions/{session['id']}/events").json()
    prompts = [event for event in acp_events if event["event_type"] == "docagent/prompt"]
    assert prompts[-1]["payload"]["prompt"] == "hello"
    assert prompts[-1]["payload"]["metadata"]["action"] == "send_message"


def test_operation_endpoints_record_prompt_action_metadata(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    assert client.post(f"/sessions/{session['id']}/loop/start").status_code == 200
    assert client.post(
        f"/sessions/{session['id']}/outline/approve",
        json={"outline_markdown": "# Outline\n"},
    ).status_code == 200
    assert client.post(
        f"/sessions/{session['id']}/revision/selection",
        json={
            "selected_text": "Define the desired product outcome.",
            "instruction": "Make it sharper",
        },
    ).status_code == 200
    assert client.post(f"/sessions/{session['id']}/checklist/run").status_code == 200
    assert client.post(f"/sessions/{session['id']}/artifacts/export-markdown").status_code == 200

    acp_events = client.get(f"/sessions/{session['id']}/events").json()
    actions = [
        event["payload"]["metadata"]["action"]
        for event in acp_events
        if event["event_type"] == "docagent/prompt"
    ]
    assert actions == [
        "start_loop",
        "approve_outline",
        "revise_selection",
        "run_checklist",
        "export_markdown",
    ]


def test_export_docx_route_creates_artifact_without_runtime_prompt(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    client.put(f"/tasks/{task['id']}/draft", json={"markdown": "# Draft\n\nBody\n"})

    before_prompts = [
        event for event in client.get(f"/sessions/{session['id']}/events").json()
        if event["event_type"] == "docagent/prompt"
    ]
    response = client.post(f"/sessions/{session['id']}/artifacts/export-docx")

    assert response.status_code == 200
    body = response.json()
    assert body["artifact_path"].endswith(".docx")
    assert (Path(task["workspace_root"]) / body["artifact_path"]).is_file()
    timeline = client.get(f"/sessions/{session['id']}/timeline").json()
    assert any(event["kind"] == "export_docx" and body["artifact_path"] in event["paths"] for event in timeline)
    after_prompts = [
        event for event in client.get(f"/sessions/{session['id']}/events").json()
        if event["event_type"] == "docagent/prompt"
    ]
    assert after_prompts == before_prompts


def test_repeated_docx_exports_create_distinct_artifacts(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    client.put(f"/tasks/{task['id']}/draft", json={"markdown": "# Draft\n\nBody\n"})

    first = client.post(f"/sessions/{session['id']}/artifacts/export-docx").json()
    second = client.post(f"/sessions/{session['id']}/artifacts/export-docx").json()

    assert first["artifact_path"] != second["artifact_path"]
    assert (Path(task["workspace_root"]) / first["artifact_path"]).is_file()
    assert (Path(task["workspace_root"]) / second["artifact_path"]).is_file()
    timeline = client.get(f"/sessions/{session['id']}/timeline").json()
    export_paths = [
        path
        for event in timeline
        if event["kind"] == "export_docx"
        for path in event["paths"]
    ]
    assert first["artifact_path"] in export_paths
    assert second["artifact_path"] in export_paths


def test_export_pdf_route_creates_artifact_without_runtime_prompt(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    client.put(f"/tasks/{task['id']}/draft", json={"markdown": "# Draft\n\nBody\n"})

    response = client.post(f"/sessions/{session['id']}/artifacts/export-pdf")

    assert response.status_code == 200
    body = response.json()
    assert body["artifact_path"].endswith(".pdf")
    artifact_path = Path(task["workspace_root"]) / body["artifact_path"]
    assert artifact_path.read_bytes().startswith(b"%PDF-")
    timeline = client.get(f"/sessions/{session['id']}/timeline").json()
    assert any(event["kind"] == "export_pdf" and body["artifact_path"] in event["paths"] for event in timeline)


def test_export_docx_route_requires_existing_draft(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    response = client.post(f"/sessions/{session['id']}/artifacts/export-docx")

    assert response.status_code == 400
    assert response.json()["detail"] == "Draft does not exist."


def test_session_state_changes_emit_status_events(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    client.post(f"/sessions/{session['id']}/loop/start")

    events = client.get(f"/sessions/{session['id']}/timeline").json()
    status_events = [event for event in events if event["kind"] == "session_status"]
    assert [event["summary"] for event in status_events] == [
        "Session status changed to running_context",
        "Session status changed to await_outline_approval",
    ]
    acp_events = client.get(f"/sessions/{session['id']}/events").json()
    acp_statuses = [event for event in acp_events if event["event_type"].startswith("session/")]
    assert [event["event_type"] for event in acp_statuses] == [
        "session/running_context",
        "session/await_outline_approval",
    ]


def test_background_message_enqueues_celery_when_queue_enabled(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setenv("DOCAGENT_QUEUE", "celery")
    delayed_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    class FakeTask:
        @staticmethod
        def delay(*args: Any, **kwargs: Any) -> None:
            delayed_calls.append((args, kwargs))

    monkeypatch.setattr("docagent_api.worker_tasks.run_session", FakeTask)
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    # Reach draft_ready via sync calls (Celery only applies to the message dispatch below)
    assert client.post(f"/sessions/{session['id']}/loop/start").status_code == 200
    assert client.post(
        f"/sessions/{session['id']}/outline/approve",
        json={"outline_markdown": "# Outline\n"},
    ).status_code == 200

    response = client.post(
        f"/sessions/{session['id']}/messages?background=true",
        json={"message": "hello"},
    )

    assert response.status_code == 202
    # previous_state is draft_ready (the state before transitioning to running_chat)
    assert delayed_calls == [(
        (
            session["id"],
            "send_prompt",
            {"prompt": "hello", "metadata": {"action": "send_message"}},
            "draft_ready",
        ),
        {},
    )]


def test_background_message_enqueues_acp_prompt_operation(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setenv("DOCAGENT_QUEUE", "celery")
    delayed_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    class FakeTask:
        @staticmethod
        def delay(*args: Any, **kwargs: Any) -> None:
            delayed_calls.append((args, kwargs))

    monkeypatch.setattr("docagent_api.worker_tasks.run_session", FakeTask)
    client = TestClient(create_app(
        state_root=tmp_path / "state",
        repo_root=Path("."),
        runtime_adapter=PromptOnlyAdapter(),
    ))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    assert client.post(f"/sessions/{session['id']}/loop/start").status_code == 200
    assert client.post(
        f"/sessions/{session['id']}/outline/approve",
        json={"outline_markdown": "# Outline\n"},
    ).status_code == 200

    response = client.post(
        f"/sessions/{session['id']}/messages?background=true",
        json={"message": "hello"},
    )

    assert response.status_code == 202
    assert delayed_calls == [(
        (
            session["id"],
            "send_prompt",
            {"prompt": "hello", "metadata": {"action": "send_message"}},
            "draft_ready",
        ),
        {},
    )]


def test_background_start_loop_enqueues_acp_prompt_operation(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setenv("DOCAGENT_QUEUE", "celery")
    delayed_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    class FakeTask:
        @staticmethod
        def delay(*args: Any, **kwargs: Any) -> None:
            delayed_calls.append((args, kwargs))

    monkeypatch.setattr("docagent_api.worker_tasks.run_session", FakeTask)
    client = TestClient(create_app(
        state_root=tmp_path / "state",
        repo_root=Path("."),
        runtime_adapter=PromptOnlyAdapter(),
    ))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    response = client.post(f"/sessions/{session['id']}/loop/start?background=true")

    assert response.status_code == 202
    assert delayed_calls == [(
        (
            session["id"],
            "send_prompt",
            {
                "prompt": "Build context files and propose an outline. Stop when outline approval is required.",
                "metadata": {"action": "start_loop"},
            },
            "idle",
        ),
        {},
    )]


def test_background_operation_rejects_concurrent_session_operation(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setenv("DOCAGENT_QUEUE", "celery")

    class FakeTask:
        @staticmethod
        def delay(*args: Any, **kwargs: Any) -> None:
            return None

    monkeypatch.setattr("docagent_api.worker_tasks.run_session", FakeTask)
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    first = client.post(f"/sessions/{session['id']}/loop/start?background=true")
    second = client.post(f"/sessions/{session['id']}/messages?background=true", json={"message": "hello"})

    assert first.status_code == 202
    assert second.status_code == 409
