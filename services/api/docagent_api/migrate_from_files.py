"""
One-time idempotent migration from .local/docagent JSON files to Postgres.

Usage:
    python -m docagent_api.migrate_from_files [--dry-run] [--state-root PATH]

Re-running is safe: uses INSERT ... ON CONFLICT DO NOTHING.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import text


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate JSON state to Postgres")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be inserted without writing")
    parser.add_argument("--state-root", default=".local/docagent", help="Path to JSON state root")
    args = parser.parse_args()

    root = Path(args.state_root)
    if not root.exists():
        print(f"State root {root} does not exist. Nothing to migrate.")
        sys.exit(0)

    inserted = migrate_from_files(root, dry_run=args.dry_run)

    if args.dry_run:
        print("Dry run complete. No data written.")
    else:
        print(f"Migration complete: {inserted['tasks']} tasks, {inserted['sessions']} sessions, {inserted['events']} timeline events inserted.")


def migrate_from_files(root: Path, dry_run: bool = False) -> dict[str, int]:
    """Migrate JSON state files under root into the configured Postgres database."""

    from docagent_api.db import create_db_engine, create_tables
    engine = create_db_engine()
    create_tables(engine)

    tasks = _read_map(root / "tasks.json")
    sessions = _read_map(root / "sessions.json")
    timeline_events: dict[str, list[dict[str, Any]]] = {}
    for path in sorted((root / "timelines").glob("*.json")):
        session_id = path.stem
        timeline_events[session_id] = json.loads(path.read_text(encoding="utf-8"))

    inserted = {"tasks": 0, "sessions": 0, "events": 0}

    with engine.connect() as conn:
        for task_id, task in tasks.items():
            if dry_run:
                print(f"  [dry-run] INSERT task {task_id}")
            else:
                columns = ["id", "doc_type_id", "brief", "title", "description"]
                values = [":id", ":doc_type_id", ":brief", ":title", ":description"]
                params = {
                    "id": task["id"],
                    "doc_type_id": task.get("doc_type_id", ""),
                    "brief": task.get("brief", ""),
                    "title": task.get("title"),
                    "description": task.get("description"),
                }
                _add_optional_timestamp(columns, values, params, "created_at", task.get("created_at"))
                _add_optional_timestamp(columns, values, params, "updated_at", task.get("updated_at"))
                result = conn.execute(text(f"""
                    INSERT INTO tasks ({", ".join(columns)})
                    VALUES ({", ".join(values)})
                    ON CONFLICT (id) DO NOTHING
                """), params)
                inserted["tasks"] += result.rowcount

        for session_id, session in sessions.items():
            if dry_run:
                print(f"  [dry-run] INSERT session {session_id}")
            else:
                columns = ["id", "task_id", "status"]
                values = [":id", ":task_id", ":status"]
                params = {
                    "id": session["id"],
                    "task_id": session["task_id"],
                    "status": session.get("status", "pending"),
                }
                _add_optional_timestamp(columns, values, params, "created_at", session.get("created_at"))
                _add_optional_timestamp(columns, values, params, "updated_at", session.get("updated_at"))
                result = conn.execute(text(f"""
                    INSERT INTO sessions ({", ".join(columns)})
                    VALUES ({", ".join(values)})
                    ON CONFLICT (id) DO NOTHING
                """), params)
                inserted["sessions"] += result.rowcount

        for session_id, events in timeline_events.items():
            for event in events:
                if dry_run:
                    print(f"  [dry-run] INSERT timeline event {event.get('id')} for session {session_id}")
                else:
                    result = conn.execute(text("""
                        INSERT INTO timeline_events (session_id, event_type, payload)
                        SELECT :session_id, :event_type, CAST(:payload AS jsonb)
                        WHERE NOT EXISTS (
                            SELECT 1 FROM timeline_events
                            WHERE session_id = :session_id AND payload->>'id' = :event_id
                        )
                    """), {
                        "session_id": session_id,
                        "event_type": event.get("kind", "unknown"),
                        "payload": json.dumps(event),
                        "event_id": event.get("id", ""),
                    })
                    inserted["events"] += result.rowcount

        if not dry_run:
            conn.commit()

    return inserted


def _read_map(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _add_optional_timestamp(
    columns: list[str],
    values: list[str],
    params: dict[str, Any],
    key: str,
    value: Any,
) -> None:
    if not value:
        return
    columns.append(key)
    values.append(f":{key}")
    params[key] = value


if __name__ == "__main__":
    main()
