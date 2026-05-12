from unittest.mock import MagicMock, patch

from docagent_api.worker_tasks import run_session


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
