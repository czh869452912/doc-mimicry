from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from docagent_contracts import RawRuntimeEvent
from docagent_api.db import (
    RawRuntimeEventRow,
    SessionRow,
    TaskRow,
    TimelineEventRow,
    create_db_engine,
    create_session_factory,
    create_tables,
)


def _normalized_task(task: dict[str, Any]) -> dict[str, Any]:
    next_task = dict(task)
    description = str(next_task.get("description") or next_task.get("brief") or "")
    first_line = next((line.strip() for line in description.splitlines() if line.strip()), "Untitled workspace")
    next_task["description"] = description
    next_task["brief"] = str(next_task.get("brief") or description)
    next_task["title"] = str(next_task.get("title") or first_line[:80])
    return next_task


class DocAgentState:
    def __init__(self, root: Path, database_url: str | None = None) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "workspaces").mkdir(parents=True, exist_ok=True)
        self._engine = create_db_engine(database_url)
        self._Session = create_session_factory(self._engine)
        create_tables(self._engine)

    # ── tasks ─────────────────────────────────────────────────────────────────

    def list_tasks(self) -> list[dict[str, Any]]:
        with self._Session() as db:
            rows = db.query(TaskRow).all()
            return [_normalized_task(_task_row_to_dict(r)) for r in rows]

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._Session() as db:
            row = db.get(TaskRow, task_id)
            return _normalized_task(_task_row_to_dict(row)) if row is not None else None

    def save_task(self, task: dict[str, Any]) -> None:
        with self._Session() as db:
            existing = db.get(TaskRow, task["id"])
            if existing is None:
                db.add(TaskRow(
                    id=task["id"],
                    doc_type_id=task["doc_type_id"],
                    brief=task.get("brief", ""),
                    title=task.get("title"),
                    description=task.get("description"),
                    created_at=task.get("created_at", ""),
                    updated_at=task.get("updated_at", ""),
                ))
            else:
                existing.doc_type_id = task["doc_type_id"]
                existing.brief = task.get("brief", "")
                existing.title = task.get("title")
                existing.description = task.get("description")
                existing.updated_at = task.get("updated_at", existing.updated_at)
            db.commit()

    # ── sessions ──────────────────────────────────────────────────────────────

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._Session() as db:
            rows = db.query(SessionRow).all()
            return [_session_row_to_dict(r) for r in rows]

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self._Session() as db:
            row = db.get(SessionRow, session_id)
            return _session_row_to_dict(row) if row is not None else None

    def save_session(self, session: dict[str, Any]) -> None:
        with self._Session() as db:
            existing = db.get(SessionRow, session["id"])
            if existing is None:
                db.add(SessionRow(
                    id=session["id"],
                    task_id=session["task_id"],
                    status=session["status"],
                    created_at=session.get("created_at", ""),
                    updated_at=session.get("updated_at", ""),
                ))
            else:
                existing.status = session["status"]
                existing.updated_at = session.get("updated_at", existing.updated_at)
            db.commit()

    # ── timeline events ───────────────────────────────────────────────────────

    def append_timeline_event(self, session_id: str, event: dict[str, Any]) -> None:
        with self._Session() as db:
            db.add(TimelineEventRow(
                session_id=session_id,
                event_type=event.get("kind", "unknown"),
                payload=event,
            ))
            db.commit()

    def list_timeline_events(self, session_id: str) -> list[dict[str, Any]]:
        with self._Session() as db:
            rows = (
                db.query(TimelineEventRow)
                .filter(TimelineEventRow.session_id == session_id)
                .order_by(TimelineEventRow.id)
                .all()
            )
            return [r.payload for r in rows]

    def list_timeline_events_after(
        self, session_id: str, after_row_id: int
    ) -> list[tuple[int, dict[str, Any]]]:
        """Returns (row_id, event_dict) pairs for events with row id > after_row_id."""
        with self._Session() as db:
            rows = (
                db.query(TimelineEventRow)
                .filter(
                    TimelineEventRow.session_id == session_id,
                    TimelineEventRow.id > after_row_id,
                )
                .order_by(TimelineEventRow.id)
                .all()
            )
            return [(r.id, r.payload) for r in rows]

    # ── raw runtime events ────────────────────────────────────────────────────

    def append_raw_runtime_event(self, session_id: str, event: RawRuntimeEvent) -> None:
        event_dict = asdict(event)
        event_dict["runtime"] = event.runtime.value
        with self._Session() as db:
            db.add(RawRuntimeEventRow(
                session_id=session_id,
                runtime=event.runtime.value,
                payload=event_dict,
            ))
            db.commit()

    def list_raw_runtime_events(self, session_id: str) -> list[dict[str, Any]]:
        with self._Session() as db:
            rows = (
                db.query(RawRuntimeEventRow)
                .filter(RawRuntimeEventRow.session_id == session_id)
                .order_by(RawRuntimeEventRow.id)
                .all()
            )
            return [r.payload for r in rows]

    # ── workspace ─────────────────────────────────────────────────────────────

    def workspace_root(self, task_id: str) -> Path:
        return self.root / "workspaces" / task_id


def _task_row_to_dict(row: TaskRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "doc_type_id": row.doc_type_id,
        "brief": row.brief,
        "title": row.title,
        "description": row.description,
        "workspace_root": "",
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _session_row_to_dict(row: SessionRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "task_id": row.task_id,
        "status": row.status,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
