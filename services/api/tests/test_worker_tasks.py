from unittest.mock import MagicMock, patch

from docagent_api.worker_tasks import run_session
from docagent_api.celery_app import celery_app
from docagent_contracts import RawRuntimeEvent, RuntimeKind, RuntimeOperationResult, RuntimeSessionState


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
    mock_adapter.send_message.return_value = MagicMock(
        session_id="s1",
        next_state=MagicMock(value="draft_ready"),
        events=[],
        raw_events=[],
    )

    with patch("docagent_api.worker_tasks._get_state", return_value=mock_state), \
         patch("docagent_api.worker_tasks._get_adapter", return_value=mock_adapter):
        run_session("s1", "send_message", {"message": "Hello"})

    mock_adapter.send_message.assert_called_once_with("s1", message="Hello")
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
    mock_adapter.start_loop.return_value = RuntimeOperationResult(
        session_id="s1",
        next_state=RuntimeSessionState.AWAIT_OUTLINE_APPROVAL,
    )

    with patch("docagent_api.worker_tasks._get_state", return_value=mock_state), \
         patch("docagent_api.worker_tasks._get_adapter", return_value=mock_adapter), \
         patch("docagent_api.worker_tasks.build_prompt_bundle") as build_prompt_bundle:
        build_prompt_bundle.return_value = MagicMock()
        run_session("s1", "start_loop", {})

    mock_adapter.create_session.assert_called_once()
    mock_state.bind_runtime_session.assert_called_once_with("s1", "openhands", "oh-001")
    mock_adapter.start_loop.assert_called_once_with("s1")


def test_run_session_rolls_back_to_previous_state_on_failure(tmp_path):
    """On exception, session must revert to previous_state_on_failure, not the running_* state."""
    mock_state = MagicMock()
    # Session is already in running_chat (as set by start_background_runtime_operation before enqueue)
    mock_state.get_session.return_value = {"id": "s1", "task_id": "t1", "status": "running_chat"}
    mock_adapter = MagicMock()
    mock_adapter.send_message.side_effect = RuntimeError("timeout")

    saved_statuses = []

    def capture_save(session):
        saved_statuses.append(session["status"])

    mock_state.save_session.side_effect = capture_save

    with patch("docagent_api.worker_tasks._get_state", return_value=mock_state), \
         patch("docagent_api.worker_tasks._get_adapter", return_value=mock_adapter):
        # previous_state_on_failure = "draft_ready" (state before the transition)
        run_session("s1", "send_message", {"message": "Hello"}, previous_state_on_failure="draft_ready")

    # Must roll back to draft_ready, not running_chat
    assert saved_statuses[-1] == "draft_ready"


def test_run_session_missing_previous_state_fails_running_session(tmp_path):
    mock_state = MagicMock()
    mock_state.get_session.return_value = {"id": "s1", "task_id": "t1", "status": "running_chat"}
    mock_adapter = MagicMock()
    mock_adapter.send_message.side_effect = RuntimeError("timeout")

    saved_statuses = []

    def capture_save(session):
        saved_statuses.append(session["status"])

    mock_state.save_session.side_effect = capture_save

    with patch("docagent_api.worker_tasks._get_state", return_value=mock_state), \
         patch("docagent_api.worker_tasks._get_adapter", return_value=mock_adapter):
        run_session("s1", "send_message", {"message": "Hello"})

    assert saved_statuses[-1] == "failed"


def test_run_session_uses_streaming_method_with_runtime_event_sink(tmp_path):
    mock_state = MagicMock()
    mock_state.get_session.return_value = {"id": "s1", "task_id": "t1", "status": "running_context"}
    streamed_event = RawRuntimeEvent(
        id="raw-001",
        session_id="s1",
        runtime=RuntimeKind.OPENHANDS,
        runtime_session_id="oh-001",
        kind="file_written",
        payload={"path": "draft/outline.md"},
        created_at="2026-05-12T00:00:00Z",
    )

    class StreamingAdapter:
        def get_state(self, session_id):
            return RuntimeSessionState.RUNNING_CONTEXT

        def start_loop_stream(self, session_id, sink):
            sink(streamed_event)
            return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.AWAIT_OUTLINE_APPROVAL)

        def start_loop(self, session_id):
            raise AssertionError("sync method should not be used when stream method exists")

    with patch("docagent_api.worker_tasks._get_state", return_value=mock_state), \
         patch("docagent_api.worker_tasks._get_adapter", return_value=StreamingAdapter()):
        run_session("s1", "start_loop_stream", {})

    mock_state.append_raw_runtime_event.assert_called_once_with("s1", streamed_event)
    saved_statuses = [call.args[0]["status"] for call in mock_state.save_session.call_args_list]
    assert saved_statuses[-1] == "await_outline_approval"


def test_run_session_does_not_write_final_result_after_cancel(tmp_path):
    mock_state = MagicMock()
    mock_state.get_session.side_effect = [
        {"id": "s1", "task_id": "t1", "status": "running_chat"},
        {"id": "s1", "task_id": "t1", "status": "cancelled"},
    ]
    mock_adapter = MagicMock()
    mock_adapter.get_state.return_value = RuntimeSessionState.RUNNING_CHAT
    mock_adapter.send_message.return_value = RuntimeOperationResult(
        session_id="s1",
        next_state=RuntimeSessionState.DRAFT_READY,
    )

    with patch("docagent_api.worker_tasks._get_state", return_value=mock_state), \
         patch("docagent_api.worker_tasks._get_adapter", return_value=mock_adapter):
        run_session("s1", "send_message", {"message": "Hello"})

    mock_adapter.send_message.assert_called_once_with("s1", message="Hello")
    mock_state.append_timeline_event.assert_not_called()
    mock_state.save_session.assert_not_called()
    mock_state.release_operation_lease.assert_called_once_with("s1")
