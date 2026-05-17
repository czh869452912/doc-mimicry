from unittest.mock import MagicMock, patch

import docagent_api.worker_tasks as worker_tasks
from docagent_api.worker_tasks import run_session
from docagent_api.celery_app import celery_app
from docagent_contracts import AcpRuntimeUpdate, RawRuntimeEvent, RuntimeKind, RuntimeOperationResult, RuntimeSessionState


def test_run_session_calls_runtime_adapter(tmp_path):
    mock_state = MagicMock()
    mock_state.get_session.return_value = {
        "id": "s1",
        "task_id": "t1",
        "status": "pending",
        "runtime": "openhands",
        "runtime_session_id": "oh-001",
    }
    mock_state.get_task.return_value = {
        "id": "t1",
        "doc_type_id": "prd",
        "brief": "b",
        "workspace_root": str(tmp_path),
    }
    mock_adapter = MagicMock()
    mock_adapter.bind_runtime_session.return_value = None
    mock_adapter.send_prompt.return_value = MagicMock(
        session_id="s1",
        next_state=MagicMock(value="draft_ready"),
        events=[],
        raw_events=[],
        acp_updates=[],
    )

    with patch("docagent_api.worker_tasks._get_state", return_value=mock_state), \
         patch("docagent_api.worker_tasks._get_adapter", return_value=mock_adapter):
        run_session("s1", "send_prompt", {"prompt": "Hello", "metadata": {"action": "send_message"}})

    mock_adapter.send_prompt.assert_called_once_with("s1", prompt="Hello", metadata={"action": "send_message"})
    mock_adapter.create_session.assert_not_called()
    mock_adapter.bind_runtime_session.assert_called_once()


def test_celery_worker_preserves_real_standard_streams_for_runtime_sdks():
    assert celery_app.conf.worker_redirect_stdouts is False


def test_run_session_creates_openhands_runtime_session_in_worker_when_unbound(tmp_path):
    mock_state = MagicMock()
    mock_state.get_session.return_value = {
        "id": "s1",
        "task_id": "t1",
        "status": "running_context",
        "runtime": "openhands",
    }
    mock_state.get_task.return_value = {
        "id": "t1",
        "doc_type_id": "prd",
        "brief": "b",
        "workspace_root": str(tmp_path),
    }
    mock_adapter = MagicMock()
    mock_adapter.get_state.side_effect = RuntimeError("not bound")
    mock_adapter.create_session.return_value = RuntimeOperationResult(
        session_id="s1",
        next_state=RuntimeSessionState.IDLE,
    )
    mock_adapter.send_prompt.return_value = RuntimeOperationResult(
        session_id="s1",
        next_state=RuntimeSessionState.AWAIT_OUTLINE_APPROVAL,
        raw_events=[
            RawRuntimeEvent(
                id="raw-create",
                session_id="s1",
                runtime=RuntimeKind.OPENHANDS,
                runtime_session_id="oh-001",
                kind="session_created",
                payload={"workspace_root": str(tmp_path)},
                created_at="2026-05-12T00:00:00Z",
            )
        ],
    )

    with patch("docagent_api.worker_tasks._get_state", return_value=mock_state), \
         patch("docagent_api.worker_tasks._get_adapter", return_value=mock_adapter), \
         patch("docagent_api.worker_tasks.build_prompt_bundle") as build_prompt_bundle:
        build_prompt_bundle.return_value = MagicMock()
        run_session("s1", "send_prompt", {"prompt": "Build context", "metadata": {"action": "start_loop"}})

    mock_adapter.create_session.assert_called_once()
    mock_state.bind_runtime_session.assert_called_once_with("s1", "openhands", "oh-001")
    mock_adapter.send_prompt.assert_called_once_with(
        "s1",
        prompt="Build context",
        metadata={"action": "start_loop"},
    )


def test_worker_reuses_runtime_adapter_within_process(monkeypatch):
    created = []

    def create_adapter():
        adapter = MagicMock()
        created.append(adapter)
        return adapter

    monkeypatch.setattr(worker_tasks, "_ADAPTER", None)
    monkeypatch.setattr("docagent_api.runtime_factory.create_runtime_adapter", create_adapter)

    first = worker_tasks._get_adapter()
    second = worker_tasks._get_adapter()

    assert first is second
    assert created == [first]


def test_run_session_fails_when_persisted_openhands_session_cannot_rebind(tmp_path):
    mock_state = MagicMock()
    mock_state.get_session.return_value = {
        "id": "s1",
        "task_id": "t1",
        "status": "running_chat",
        "runtime": "openhands",
        "runtime_session_id": "old-oh-001",
    }
    mock_state.get_task.return_value = {
        "id": "t1",
        "doc_type_id": "prd",
        "brief": "b",
        "workspace_root": str(tmp_path),
    }
    mock_adapter = MagicMock()
    mock_adapter.bind_runtime_session.return_value = False
    saved_statuses = []

    def capture_save(session):
        saved_statuses.append(session["status"])

    mock_state.save_session.side_effect = capture_save

    with patch("docagent_api.worker_tasks._get_state", return_value=mock_state), \
         patch("docagent_api.worker_tasks._get_adapter", return_value=mock_adapter), \
         patch("docagent_api.worker_tasks.build_prompt_bundle") as build_prompt_bundle:
        build_prompt_bundle.return_value = MagicMock()
        run_session(
            "s1",
            "send_prompt",
            {"prompt": "Hello", "metadata": {"action": "send_message"}},
            previous_state_on_failure="draft_ready",
        )

    mock_adapter.bind_runtime_session.assert_called_once_with("s1", "old-oh-001", RuntimeSessionState.RUNNING_CHAT)
    mock_adapter.create_session.assert_not_called()
    mock_adapter.send_prompt.assert_not_called()
    mock_state.bind_runtime_session.assert_not_called()
    assert saved_statuses[-1] == "draft_ready"
    assert any(
        "could not be rebound" in call.args[1].get("message", "")
        for call in mock_state.append_acp_event.call_args_list
    )


def test_run_session_rolls_back_to_previous_state_on_failure(tmp_path):
    """On exception, session must revert to previous_state_on_failure, not the running_* state."""
    mock_state = MagicMock()
    # Session is already in running_chat (as set by start_background_runtime_operation before enqueue)
    mock_state.get_session.return_value = {"id": "s1", "task_id": "t1", "status": "running_chat"}
    mock_adapter = MagicMock()
    mock_adapter.send_prompt.side_effect = RuntimeError("timeout")

    saved_statuses = []

    def capture_save(session):
        saved_statuses.append(session["status"])

    mock_state.save_session.side_effect = capture_save

    with patch("docagent_api.worker_tasks._get_state", return_value=mock_state), \
         patch("docagent_api.worker_tasks._get_adapter", return_value=mock_adapter):
        # previous_state_on_failure = "draft_ready" (state before the transition)
        run_session(
            "s1",
            "send_prompt",
            {"prompt": "Hello", "metadata": {"action": "send_message"}},
            previous_state_on_failure="draft_ready",
        )

    # Must roll back to draft_ready, not running_chat
    assert saved_statuses[-1] == "draft_ready"


def test_run_session_missing_previous_state_fails_running_session(tmp_path):
    mock_state = MagicMock()
    mock_state.get_session.return_value = {"id": "s1", "task_id": "t1", "status": "running_chat"}
    mock_adapter = MagicMock()
    mock_adapter.send_prompt.side_effect = RuntimeError("timeout")

    saved_statuses = []

    def capture_save(session):
        saved_statuses.append(session["status"])

    mock_state.save_session.side_effect = capture_save

    with patch("docagent_api.worker_tasks._get_state", return_value=mock_state), \
         patch("docagent_api.worker_tasks._get_adapter", return_value=mock_adapter):
        run_session("s1", "send_prompt", {"prompt": "Hello", "metadata": {"action": "send_message"}})

    assert saved_statuses[-1] == "failed"


def test_run_session_persists_acp_updates_from_prompt_result(tmp_path):
    mock_state = MagicMock()
    mock_state.get_session.return_value = {"id": "s1", "task_id": "t1", "status": "running_chat"}

    class PromptAdapter:
        def get_state(self, session_id):
            return RuntimeSessionState.RUNNING_CHAT

        def send_prompt(self, session_id, prompt, metadata):
            return RuntimeOperationResult(
                session_id=session_id,
                next_state=RuntimeSessionState.DRAFT_READY,
                acp_updates=[
                    AcpRuntimeUpdate(
                        session_id=session_id,
                        event_type="message_delta",
                        payload={"role": "assistant", "content": prompt},
                    )
                ],
            )

    with patch("docagent_api.worker_tasks._get_state", return_value=mock_state), \
         patch("docagent_api.worker_tasks._get_adapter", return_value=PromptAdapter()):
        run_session("s1", "send_prompt", {"prompt": "hello", "metadata": {"action": "send_message"}})

    mock_state.append_acp_event.assert_any_call(
        "s1",
        {"role": "assistant", "content": "hello", "event_type": "message_delta"},
        projection={},
    )
    saved_statuses = [call.args[0]["status"] for call in mock_state.save_session.call_args_list]
    assert saved_statuses[-1] == "draft_ready"


def test_run_session_rejects_legacy_background_operation_names(tmp_path):
    mock_state = MagicMock()
    mock_state.get_session.return_value = {"id": "s1", "task_id": "t1", "status": "running_context"}
    mock_adapter = MagicMock()
    mock_adapter.get_state.return_value = RuntimeSessionState.RUNNING_CONTEXT

    with patch("docagent_api.worker_tasks._get_state", return_value=mock_state), \
         patch("docagent_api.worker_tasks._get_adapter", return_value=mock_adapter):
        run_session("s1", "start_loop", {})

    mock_adapter.start_loop.assert_not_called()
    failure_events = [
        call.args[1]
        for call in mock_state.append_acp_event.call_args_list
        if call.args[0] == "s1"
    ]
    assert any(
        event.get("method") == "runtime/error"
        and "send_prompt" in event.get("message", "")
        for event in failure_events
    )


def test_run_session_persists_raw_events_from_prompt_result(tmp_path):
    mock_state = MagicMock()
    mock_state.get_session.return_value = {"id": "s1", "task_id": "t1", "status": "running_chat"}
    raw_event = RawRuntimeEvent(
        id="raw-001",
        session_id="s1",
        runtime=RuntimeKind.OPENHANDS,
        runtime_session_id="oh-001",
        kind="file_written",
        payload={"path": "draft/outline.md"},
        created_at="2026-05-12T00:00:00Z",
    )

    class PromptAdapter:
        def get_state(self, session_id):
            return RuntimeSessionState.RUNNING_CHAT

        def send_prompt(self, session_id, prompt, metadata):
            return RuntimeOperationResult(
                session_id=session_id,
                next_state=RuntimeSessionState.DRAFT_READY,
                raw_events=[raw_event],
            )

    with patch("docagent_api.worker_tasks._get_state", return_value=mock_state), \
         patch("docagent_api.worker_tasks._get_adapter", return_value=PromptAdapter()):
        run_session("s1", "send_prompt", {"prompt": "hello", "metadata": {"action": "send_message"}})

    mock_state.append_raw_runtime_event.assert_called_once_with("s1", raw_event)
    saved_statuses = [call.args[0]["status"] for call in mock_state.save_session.call_args_list]
    assert saved_statuses[-1] == "draft_ready"


def test_run_session_does_not_write_final_result_after_cancel(tmp_path):
    mock_state = MagicMock()
    mock_state.get_session.side_effect = [
        {"id": "s1", "task_id": "t1", "status": "running_chat"},
        {"id": "s1", "task_id": "t1", "status": "cancelled"},
    ]
    mock_adapter = MagicMock()
    mock_adapter.get_state.return_value = RuntimeSessionState.RUNNING_CHAT
    mock_adapter.send_prompt.return_value = RuntimeOperationResult(
        session_id="s1",
        next_state=RuntimeSessionState.DRAFT_READY,
    )

    with patch("docagent_api.worker_tasks._get_state", return_value=mock_state), \
         patch("docagent_api.worker_tasks._get_adapter", return_value=mock_adapter):
        run_session("s1", "send_prompt", {"prompt": "Hello", "metadata": {"action": "send_message"}})

    mock_adapter.send_prompt.assert_called_once_with("s1", prompt="Hello", metadata={"action": "send_message"})
    mock_state.append_timeline_event.assert_not_called()
    mock_state.save_session.assert_not_called()
    mock_state.release_operation_lease.assert_called_once_with("s1")
