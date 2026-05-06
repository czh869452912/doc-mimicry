from pathlib import Path

from docagent_api.state import DocAgentState
from docagent_contracts import RawRuntimeEvent, RuntimeKind


def test_state_starts_with_empty_collections(tmp_path: Path) -> None:
    state = DocAgentState(tmp_path)

    assert state.list_tasks() == []
    assert state.list_sessions() == []


def test_state_persists_task_and_session(tmp_path: Path) -> None:
    state = DocAgentState(tmp_path)
    task = {
        "id": "task-001",
        "doc_type_id": "prd",
        "brief": "Draft a PRD",
        "workspace_root": "workspaces/task-001",
        "created_at": "2026-04-30T00:00:00Z",
        "updated_at": "2026-04-30T00:00:00Z",
    }
    session = {
        "id": "session-001",
        "task_id": "task-001",
        "status": "idle",
        "created_at": "2026-04-30T00:00:00Z",
        "updated_at": "2026-04-30T00:00:00Z",
    }

    state.save_task(task)
    state.save_session(session)
    reloaded = DocAgentState(tmp_path)

    assert reloaded.get_task("task-001") == task
    assert reloaded.get_session("session-001") == session


def test_state_persists_raw_runtime_events(tmp_path: Path) -> None:
    state = DocAgentState(tmp_path)
    event = RawRuntimeEvent(
        id="raw-001",
        session_id="session-001",
        runtime=RuntimeKind.OPENHANDS,
        runtime_session_id="openhands-001",
        kind="file_written",
        payload={"path": "draft/draft.md"},
        created_at="2026-05-06T00:00:00Z",
    )

    state.append_raw_runtime_event("session-001", event)
    state.append_raw_runtime_event("session-001", event)

    assert state.list_raw_runtime_events("session-001") == [
        {
            "id": "raw-001",
            "session_id": "session-001",
            "runtime": "openhands",
            "runtime_session_id": "openhands-001",
            "kind": "file_written",
            "payload": {"path": "draft/draft.md"},
            "created_at": "2026-05-06T00:00:00Z",
        },
        {
            "id": "raw-001",
            "session_id": "session-001",
            "runtime": "openhands",
            "runtime_session_id": "openhands-001",
            "kind": "file_written",
            "payload": {"path": "draft/draft.md"},
            "created_at": "2026-05-06T00:00:00Z",
        },
    ]
    assert (tmp_path / "raw-events" / "session-001.jsonl").exists()
