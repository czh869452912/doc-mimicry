from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

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

    assert reloaded.get_task("task-001") == {
        **task,
        "title": "Draft a PRD",
        "description": "Draft a PRD",
    }
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


def test_state_keeps_all_concurrent_timeline_appends(tmp_path: Path) -> None:
    state = DocAgentState(tmp_path)

    def append_event(index: int) -> None:
        state.append_timeline_event(
            "session-001",
            {
                "id": f"event-{index:03d}",
                "session_id": "session-001",
                "kind": "update_draft",
                "summary": f"Event {index}",
            },
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(append_event, range(40)))

    events = state.list_timeline_events("session-001")
    assert len(events) == 40
    assert {event["id"] for event in events} == {f"event-{index:03d}" for index in range(40)}


def test_append_and_list_timeline_events(pg_state) -> None:
    pg_state.save_task({
        "id": "t1", "doc_type_id": "prd", "brief": "b", "title": "T1",
        "description": "", "workspace_root": "w/t1",
        "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
    })
    pg_state.save_session({
        "id": "s1", "task_id": "t1", "status": "pending",
        "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
    })
    pg_state.append_timeline_event("s1", {
        "id": "e1", "kind": "user_message", "summary": "hi",
        "actor": "user", "paths": [], "status": "done",
        "created_at": "2026-01-01T00:00:00Z",
    })
    events = pg_state.list_timeline_events("s1")
    assert len(events) == 1
    assert events[0]["id"] == "e1"


def test_list_timeline_events_after(pg_state) -> None:
    pg_state.save_task({
        "id": "t2", "doc_type_id": "prd", "brief": "b", "title": "T2",
        "description": "", "workspace_root": "w/t2",
        "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
    })
    pg_state.save_session({
        "id": "s2", "task_id": "t2", "status": "pending",
        "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
    })
    for i in range(3):
        pg_state.append_timeline_event("s2", {
            "id": f"e{i}", "kind": "user_message", "summary": f"msg {i}",
            "actor": "user", "paths": [], "status": "done",
            "created_at": "2026-01-01T00:00:00Z",
        })
    rows = pg_state.list_timeline_events_after("s2", after_row_id=0)
    assert len(rows) == 3
    first_row_id = rows[0][0]
    later = pg_state.list_timeline_events_after("s2", after_row_id=first_row_id)
    assert len(later) == 2
