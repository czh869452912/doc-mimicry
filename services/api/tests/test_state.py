from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

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
        "workspace_root": str(tmp_path / "workspaces" / "task-001"),
        "created_at": "2026-04-30T00:00:00Z",
        "updated_at": "2026-04-30T00:00:00Z",
    }
    session = {
        "id": "session-001",
        "task_id": "task-001",
        "status": "pending",
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


def test_state_persists_runtime_binding_and_operation_metadata(tmp_path: Path) -> None:
    state = DocAgentState(tmp_path)
    state.save_task({
        "id": "task-001",
        "doc_type_id": "prd",
        "brief": "Draft a PRD",
        "created_at": "2026-05-12T00:00:00Z",
        "updated_at": "2026-05-12T00:00:00Z",
    })
    state.save_session({
        "id": "session-001",
        "task_id": "task-001",
        "status": "idle",
        "runtime": "openhands",
        "runtime_session_id": "oh-001",
        "celery_task_id": "celery-001",
        "created_at": "2026-05-12T00:00:00Z",
        "updated_at": "2026-05-12T00:00:00Z",
    })

    reloaded = DocAgentState(tmp_path)

    assert reloaded.get_session("session-001") == {
        "id": "session-001",
        "task_id": "task-001",
        "status": "idle",
        "runtime": "openhands",
        "runtime_session_id": "oh-001",
        "celery_task_id": "celery-001",
        "created_at": "2026-05-12T00:00:00Z",
        "updated_at": "2026-05-12T00:00:00Z",
    }


def test_state_acquires_and_releases_operation_lease(tmp_path: Path) -> None:
    state = DocAgentState(tmp_path)
    state.save_task({
        "id": "task-001",
        "doc_type_id": "prd",
        "brief": "Draft a PRD",
        "created_at": "2026-05-12T00:00:00Z",
        "updated_at": "2026-05-12T00:00:00Z",
    })
    state.save_session({
        "id": "session-001",
        "task_id": "task-001",
        "status": "idle",
        "created_at": "2026-05-12T00:00:00Z",
        "updated_at": "2026-05-12T00:00:00Z",
    })

    assert state.acquire_operation_lease("session-001", "celery-001") is True
    assert state.acquire_operation_lease("session-001", "celery-002") is False

    state.release_operation_lease("session-001", "celery-001")

    assert state.acquire_operation_lease("session-001", "celery-002") is True


def test_state_lists_sessions_by_task_and_status_and_marks_stale(tmp_path: Path) -> None:
    state = DocAgentState(tmp_path)
    for task_id in ("task-001", "task-002"):
        state.save_task({
            "id": task_id,
            "doc_type_id": "prd",
            "brief": "Draft a PRD",
            "created_at": "2026-05-12T00:00:00Z",
            "updated_at": "2026-05-12T00:00:00Z",
        })
    state.save_session({
        "id": "session-001",
        "task_id": "task-001",
        "status": "running_chat",
        "celery_task_id": "celery-001",
        "created_at": "2026-05-12T00:00:00Z",
        "updated_at": "2026-05-12T00:00:00Z",
    })
    state.save_session({
        "id": "session-002",
        "task_id": "task-002",
        "status": "idle",
        "created_at": "2026-05-12T00:00:00Z",
        "updated_at": "2026-05-12T00:00:00Z",
    })

    assert [s["id"] for s in state.list_sessions_by_task("task-001")] == ["session-001"]
    assert [s["id"] for s in state.list_sessions_by_status(["running_chat"])] == ["session-001"]

    state.mark_stale_operations(["running_chat"], "failed")

    stale = state.get_session("session-001")
    assert stale["status"] == "failed"
    assert "celery_task_id" not in stale


def test_state_persists_raw_runtime_events(tmp_path: Path) -> None:
    state = DocAgentState(tmp_path)
    state.save_task({
        "id": "task-001",
        "doc_type_id": "prd",
        "brief": "Draft a PRD",
        "created_at": "2026-05-06T00:00:00Z",
        "updated_at": "2026-05-06T00:00:00Z",
    })
    state.save_session({
        "id": "session-001",
        "task_id": "task-001",
        "status": "idle",
        "created_at": "2026-05-06T00:00:00Z",
        "updated_at": "2026-05-06T00:00:00Z",
    })
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


def test_state_keeps_all_concurrent_timeline_appends(tmp_path: Path) -> None:
    state = DocAgentState(tmp_path)
    state.save_task({
        "id": "task-001",
        "doc_type_id": "prd",
        "brief": "Draft a PRD",
        "created_at": "2026-05-06T00:00:00Z",
        "updated_at": "2026-05-06T00:00:00Z",
    })
    state.save_session({
        "id": "session-001",
        "task_id": "task-001",
        "status": "idle",
        "created_at": "2026-05-06T00:00:00Z",
        "updated_at": "2026-05-06T00:00:00Z",
    })

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


def test_database_enforces_session_task_foreign_key(pg_state) -> None:
    try:
        pg_state.save_session({
            "id": "orphan-session",
            "task_id": "missing-task",
            "status": "pending",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        })
    except IntegrityError:
        return
    raise AssertionError("expected session save to fail when task_id does not reference an existing task")


def test_schema_has_runtime_state_foreign_keys(pg_engine) -> None:
    inspector = inspect(pg_engine)
    session_columns = {column["name"] for column in inspector.get_columns("sessions")}
    session_fks = inspector.get_foreign_keys("sessions")
    timeline_fks = inspector.get_foreign_keys("timeline_events")
    raw_fks = inspector.get_foreign_keys("raw_runtime_events")

    assert {"runtime", "runtime_session_id", "celery_task_id"}.issubset(session_columns)
    assert any(fk["referred_table"] == "tasks" and fk["constrained_columns"] == ["task_id"] for fk in session_fks)
    assert any(fk["referred_table"] == "sessions" and fk["constrained_columns"] == ["session_id"] for fk in timeline_fks)
    assert any(fk["referred_table"] == "sessions" and fk["constrained_columns"] == ["session_id"] for fk in raw_fks)
