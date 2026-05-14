from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import update

from docagent_contracts import RawRuntimeEvent
from docagent_api.db import (
    AcpEventRow,
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
            tasks = [_normalized_task(_task_row_to_dict(r)) for r in rows]
            for task in tasks:
                task["workspace_root"] = str(self.workspace_root(task["id"]))
            return tasks

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._Session() as db:
            row = db.get(TaskRow, task_id)
            if row is None:
                return None
            task = _normalized_task(_task_row_to_dict(row))
            task["workspace_root"] = str(self.workspace_root(row.id))
            return task

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
                    created_at=_parse_iso(task.get("created_at")) or datetime.now(timezone.utc),
                    updated_at=_parse_iso(task.get("updated_at")) or datetime.now(timezone.utc),
                ))
            else:
                existing.doc_type_id = task["doc_type_id"]
                existing.brief = task.get("brief", "")
                existing.title = task.get("title")
                existing.description = task.get("description")
                existing.updated_at = _parse_iso(task.get("updated_at")) or datetime.now(timezone.utc)
            db.commit()

    # ── sessions ──────────────────────────────────────────────────────────────

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._Session() as db:
            rows = db.query(SessionRow).all()
            return [_session_row_to_dict(r) for r in rows]

    def list_sessions_by_task(self, task_id: str) -> list[dict[str, Any]]:
        with self._Session() as db:
            rows = db.query(SessionRow).filter(SessionRow.task_id == task_id).all()
            return [_session_row_to_dict(r) for r in rows]

    def list_sessions_by_status(self, statuses: list[str] | set[str]) -> list[dict[str, Any]]:
        with self._Session() as db:
            rows = db.query(SessionRow).filter(SessionRow.status.in_(list(statuses))).all()
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
                    runtime=session.get("runtime"),
                    runtime_session_id=session.get("runtime_session_id"),
                    celery_task_id=session.get("celery_task_id"),
                    created_at=_parse_iso(session.get("created_at")) or datetime.now(timezone.utc),
                    updated_at=_parse_iso(session.get("updated_at")) or datetime.now(timezone.utc),
                ))
            else:
                existing.status = session["status"]
                if "runtime" in session:
                    existing.runtime = session.get("runtime")
                if "runtime_session_id" in session:
                    existing.runtime_session_id = session.get("runtime_session_id")
                if "celery_task_id" in session:
                    existing.celery_task_id = session.get("celery_task_id")
                existing.updated_at = _parse_iso(session.get("updated_at")) or datetime.now(timezone.utc)
            db.commit()

    def bind_runtime_session(self, session_id: str, runtime: str, runtime_session_id: str) -> None:
        with self._Session() as db:
            row = db.get(SessionRow, session_id)
            if row is None:
                return
            row.runtime = runtime
            row.runtime_session_id = runtime_session_id
            row.updated_at = datetime.now(timezone.utc)
            db.commit()

    def acquire_operation_lease(self, session_id: str, celery_task_id: str) -> bool:
        with self._Session() as db:
            result = db.execute(
                update(SessionRow)
                .where(SessionRow.id == session_id)
                .where(SessionRow.celery_task_id.is_(None))
                .values(celery_task_id=celery_task_id, updated_at=datetime.now(timezone.utc))
            )
            db.commit()
            return result.rowcount == 1

    def release_operation_lease(self, session_id: str, celery_task_id: str | None = None) -> None:
        with self._Session() as db:
            row = db.get(SessionRow, session_id)
            if row is None:
                return
            if celery_task_id is not None and row.celery_task_id != celery_task_id:
                return
            row.celery_task_id = None
            row.updated_at = datetime.now(timezone.utc)
            db.commit()

    def mark_stale_operations(self, running_statuses: list[str] | set[str], next_status: str) -> list[dict[str, Any]]:
        with self._Session() as db:
            rows = db.query(SessionRow).filter(SessionRow.status.in_(list(running_statuses))).all()
            stale: list[dict[str, Any]] = []
            for row in rows:
                row.status = next_status
                row.celery_task_id = None
                row.updated_at = datetime.now(timezone.utc)
                stale.append(_session_row_to_dict(row))
            db.commit()
            return stale

    def delete_session(self, session_id: str) -> None:
        with self._Session() as db:
            row = db.get(SessionRow, session_id)
            if row is not None:
                db.delete(row)
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
            return [_with_created_at(r.payload, r.created_at) for r in rows]

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
            return [(r.id, _with_created_at(r.payload, r.created_at)) for r in rows]

    # ── ACP events ───────────────────────────────────────────────────────────

    def append_acp_event(
        self,
        session_id: str,
        payload: dict[str, Any],
        projection: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event_type = _acp_event_type(payload)
        with self._Session() as db:
            row = AcpEventRow(
                session_id=session_id,
                event_type=event_type,
                payload=payload,
                projection=projection or {},
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return _acp_event_row_to_dict(row)

    def list_acp_events(self, session_id: str) -> list[dict[str, Any]]:
        with self._Session() as db:
            rows = (
                db.query(AcpEventRow)
                .filter(AcpEventRow.session_id == session_id)
                .order_by(AcpEventRow.id)
                .all()
            )
            return [_acp_event_row_to_dict(row) for row in rows]

    def list_acp_events_after(self, session_id: str, after_sequence: int) -> list[dict[str, Any]]:
        with self._Session() as db:
            rows = (
                db.query(AcpEventRow)
                .filter(
                    AcpEventRow.session_id == session_id,
                    AcpEventRow.id > after_sequence,
                )
                .order_by(AcpEventRow.id)
                .all()
            )
            return [_acp_event_row_to_dict(row) for row in rows]

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
        "created_at": _format_iso(row.created_at),
        "updated_at": _format_iso(row.updated_at),
    }


def _session_row_to_dict(row: SessionRow) -> dict[str, Any]:
    result = {
        "id": row.id,
        "task_id": row.task_id,
        "status": row.status,
        "created_at": _format_iso(row.created_at),
        "updated_at": _format_iso(row.updated_at),
    }
    if row.runtime is not None:
        result["runtime"] = row.runtime
    if row.runtime_session_id is not None:
        result["runtime_session_id"] = row.runtime_session_id
    if row.celery_task_id is not None:
        result["celery_task_id"] = row.celery_task_id
    return result


def _parse_iso(dt_str: str | None) -> datetime | None:
    """Parse an ISO 8601 string (with Z suffix) into a timezone-aware datetime."""
    if not dt_str:
        return None
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))


def _format_iso(dt: datetime | str | None) -> str:
    """Format a datetime as an ISO 8601 string with Z suffix.

    Accepts strings defensively so the function works regardless of the
    underlying column type (Text or DateTime).
    """
    if dt is None:
        return ""
    if isinstance(dt, str):
        return dt
    return dt.isoformat().replace("+00:00", "Z")


def _with_created_at(payload: dict[str, Any], row_created_at: datetime | str | None) -> dict[str, Any]:
    """Return payload with created_at injected from the DB row if missing."""
    if payload.get("created_at"):
        return payload
    return {**payload, "created_at": _format_iso(row_created_at)}


def _acp_event_type(payload: dict[str, Any]) -> str:
    event_type = payload.get("method") or payload.get("type") or payload.get("event_type")
    return str(event_type or "unknown")


def _acp_event_row_to_dict(row: AcpEventRow) -> dict[str, Any]:
    return {
        "id": f"acp-{row.id}",
        "session_id": row.session_id,
        "sequence": row.id,
        "event_type": row.event_type,
        "payload": row.payload,
        "projection": row.projection or {},
        "created_at": _format_iso(row.created_at),
    }
