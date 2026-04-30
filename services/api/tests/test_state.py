from pathlib import Path

from docagent_api.state import DocAgentState


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
