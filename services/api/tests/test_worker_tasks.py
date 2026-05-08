from unittest.mock import MagicMock, patch

from docagent_api.worker_tasks import run_session


def test_run_session_calls_runtime_adapter(tmp_path):
    mock_state = MagicMock()
    mock_state.get_session.return_value = {"id": "s1", "task_id": "t1", "status": "pending"}
    mock_state.get_task.return_value = {
        "id": "t1",
        "doc_type_id": "prd",
        "brief": "b",
        "workspace_root": str(tmp_path),
    }
    mock_adapter = MagicMock()
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
