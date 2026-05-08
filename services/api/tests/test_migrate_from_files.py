from __future__ import annotations

import json

from docagent_api.migrate_from_files import migrate_from_files
from docagent_api.state import DocAgentState


def test_migrate_from_files_handles_legacy_records_without_timestamps(pg_engine, tmp_path, monkeypatch) -> None:
    state_root = tmp_path / "legacy"
    state_root.mkdir()
    (state_root / "timelines").mkdir()
    (state_root / "tasks.json").write_text(
        json.dumps({
            "task-1": {
                "id": "task-1",
                "doc_type_id": "prd",
                "brief": "Legacy task",
            },
        }),
        encoding="utf-8",
    )
    (state_root / "sessions.json").write_text(
        json.dumps({
            "session-1": {
                "id": "session-1",
                "task_id": "task-1",
                "status": "pending",
            },
        }),
        encoding="utf-8",
    )
    (state_root / "timelines" / "session-1.json").write_text(
        json.dumps([{"id": "event-1", "kind": "user_message", "summary": "hello"}]),
        encoding="utf-8",
    )
    monkeypatch.setenv("DATABASE_URL", pg_engine.url.render_as_string(hide_password=False))

    inserted = migrate_from_files(state_root, dry_run=False)

    state = DocAgentState(tmp_path / "state")
    assert inserted == {"tasks": 1, "sessions": 1, "events": 1}
    assert state.get_task("task-1") is not None
    assert state.get_session("session-1") is not None
    [event] = state.list_timeline_events("session-1")
    assert event["id"] == "event-1"
    assert event["created_at"]
