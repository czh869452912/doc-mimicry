# Backend Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace JSON file-backed `DocAgentState` and `ThreadPoolExecutor` background runner with PostgreSQL (SQLAlchemy sync + psycopg2), Celery + Redis worker queue, and a Docker Compose single-machine deployment.

**Architecture:** `DocAgentState` interface is preserved — only the implementation changes. SQLAlchemy sync ORM models replace the JSON file read/write pattern. The SSE endpoint uses incremental Postgres polling (`WHERE id > last_seen_id`) via `asyncio.to_thread`. Celery replaces `BackgroundRuntimeRunner` for durable background job execution; `BackgroundRuntimeRunner` is kept as an `inline` dev fallback. Alembic manages schema migrations. Docker Compose wires all five services with named volumes.

**Tech Stack:** FastAPI, SQLAlchemy 2 (sync, psycopg2 driver), Alembic, Celery 5, Redis 7, psycopg2-binary, testcontainers-python, pytest-asyncio, Docker Compose v2.

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `services/api/docagent_api/db.py` | SQLAlchemy engine + session factory + ORM models |
| Create | `services/api/alembic/` | Alembic env + initial migration |
| Modify | `services/api/docagent_api/state.py` | Replace JSON impl with SQLAlchemy |
| Modify | `services/api/docagent_api/app.py` | Use DB-backed state; remove `_recover_interrupted_sessions` |
| Create | `services/api/docagent_api/celery_app.py` | Celery app with recovery config |
| Create | `services/api/docagent_api/worker_tasks.py` | `run_session` Celery task |
| Modify | `services/api/docagent_api/routes/_shared.py` | `start_background_runtime_operation` queues via Celery |
| Modify | `services/api/docagent_api/routes/sessions.py` | SSE uses incremental Postgres polling |
| Create | `services/api/docagent_api/migrate_from_files.py` | Idempotent migration from `.local/docagent` |
| Create | `docker-compose.yml` | Production service definitions |
| Create | `docker-compose.override.yml` | Dev hot-reload overrides |
| Create | `.env.example` | Environment variable template |
| Modify | `services/api/tests/conftest.py` | Postgres test fixture with transaction rollback |
| Modify | `services/api/tests/test_state.py` | Update for DB-backed state |
| Modify | `services/api/tests/test_api.py` | Update fixture to use DB-backed state |
| Modify | `services/api/requirements.txt` (or `pyproject.toml`) | Add psycopg2-binary, celery, redis, alembic, sqlalchemy |

---

### Task 1: Add SQLAlchemy dependencies and create `db.py`

**Files:**
- Modify: `services/api/requirements.txt` (add deps)
- Create: `services/api/docagent_api/db.py`

- [ ] **Step 1: Confirm existing dependency file format**

```bash
cat services/api/requirements.txt 2>/dev/null || cat services/api/pyproject.toml 2>/dev/null | head -40
```

Note whether the project uses `requirements.txt` or `pyproject.toml`. Steps below show `requirements.txt`; adapt if needed.

- [ ] **Step 2: Add new dependencies**

Add to `services/api/requirements.txt`:

```
sqlalchemy>=2.0
psycopg2-binary>=2.9
alembic>=1.13
celery[redis]>=5.3
redis>=5.0
```

Install:

```bash
cd services/api
.local/dev/.venv/Scripts/pip.exe install sqlalchemy psycopg2-binary alembic "celery[redis]" redis
```

- [ ] **Step 3: Create `db.py` with engine, session factory, and ORM models**

Create `services/api/docagent_api/db.py`:

```python
from __future__ import annotations

import json
import os
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Index,
    String,
    Text,
    create_engine,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.sql import func, text

_DATABASE_URL_ENV = "DATABASE_URL"
_DEFAULT_DATABASE_URL = "postgresql+psycopg2://docagent:docagent@localhost:5432/docagent"

VALID_SESSION_STATUSES = (
    "pending",
    "running_context",
    "await_outline_approval",
    "running_draft",
    "draft_ready",
    "running_revision",
    "running_chat",
    "running_checklist",
    "running_export",
    "failed",
    "cancelled",
    "completed",
)


class Base(DeclarativeBase):
    pass


class TaskRow(Base):
    __tablename__ = "tasks"
    id = Column(String, primary_key=True)
    doc_type_id = Column(String, nullable=False)
    brief = Column(Text, nullable=False)
    title = Column(Text)
    description = Column(Text)
    created_at = Column(Text, nullable=False, server_default=func.now())
    updated_at = Column(Text, nullable=False, server_default=func.now(), onupdate=func.now())


class SessionRow(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True)
    task_id = Column(String, nullable=False)
    status = Column(
        String,
        CheckConstraint(f"status IN ({', '.join(repr(s) for s in VALID_SESSION_STATUSES)})"),
        nullable=False,
    )
    created_at = Column(Text, nullable=False, server_default=func.now())
    updated_at = Column(Text, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (Index("idx_sessions_task_id", "task_id"),)


class TimelineEventRow(Base):
    __tablename__ = "timeline_events"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    payload = Column(JSONB, nullable=False)
    created_at = Column(Text, nullable=False, server_default=func.now())

    __table_args__ = (Index("idx_timeline_session_id", "session_id", "id"),)


class RawRuntimeEventRow(Base):
    __tablename__ = "raw_runtime_events"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False)
    runtime = Column(String, nullable=False)
    payload = Column(JSONB, nullable=False)
    created_at = Column(Text, nullable=False, server_default=func.now())

    __table_args__ = (Index("idx_raw_events_session_id", "session_id"),)


def get_database_url() -> str:
    return os.environ.get(_DATABASE_URL_ENV, _DEFAULT_DATABASE_URL)


def create_db_engine(database_url: str | None = None):
    url = database_url or get_database_url()
    return create_engine(
        url,
        pool_size=int(os.environ.get("DB_POOL_SIZE", "5")),
        max_overflow=int(os.environ.get("DB_MAX_OVERFLOW", "10")),
        pool_timeout=30,
        pool_recycle=1800,
    )


def create_session_factory(engine) -> sessionmaker:
    return sessionmaker(bind=engine)


def create_tables(engine) -> None:
    Base.metadata.create_all(engine)
```

- [ ] **Step 4: Write a test that the engine connects**

In `services/api/tests/test_db.py` (create it):

```python
import pytest
from docagent_api.db import create_db_engine, create_tables, Base


def test_create_tables_succeeds(pg_engine):
    # pg_engine fixture provided by conftest.py in Task 8
    create_tables(pg_engine)
    from sqlalchemy import inspect
    inspector = inspect(pg_engine)
    tables = inspector.get_table_names()
    assert "tasks" in tables
    assert "sessions" in tables
    assert "timeline_events" in tables
    assert "raw_runtime_events" in tables
```

This test will be wired once `pg_engine` fixture exists (Task 8). Skip for now — mark it as expected-to-be-wired.

- [ ] **Step 5: Verify import works**

```bash
cd services/api
.local/dev/.venv/Scripts/python.exe -c "from docagent_api.db import create_db_engine; print('ok')"
```

Expected: `ok`.

- [ ] **Step 6: Commit**

```bash
git add services/api/docagent_api/db.py services/api/requirements.txt
git commit -m "feat: add SQLAlchemy ORM models and engine factory"
```

---

### Task 2: Set up Alembic and create the initial migration

**Files:**
- Create: `services/api/alembic/` (directory with env.py + first migration)
- Create: `services/api/alembic.ini`

- [ ] **Step 1: Initialise Alembic**

```bash
cd services/api
.local/dev/.venv/Scripts/alembic.exe init alembic
```

Expected: creates `alembic/` directory and `alembic.ini`.

- [ ] **Step 2: Configure `alembic/env.py` to use the app's models**

Replace the `target_metadata` block in `services/api/alembic/env.py`. Find the line:

```python
target_metadata = None
```

Replace it with:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from docagent_api.db import Base, get_database_url
target_metadata = Base.metadata
```

Also update `run_migrations_online` to use `get_database_url()`:

```python
def run_migrations_online() -> None:
    from sqlalchemy import engine_from_config
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url()
    connectable = engine_from_config(configuration, prefix="sqlalchemy.")
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
```

- [ ] **Step 3: Update `alembic.ini` to not hard-code URL**

In `services/api/alembic.ini`, set:

```ini
sqlalchemy.url = %(DATABASE_URL)s
```

This is overridden by `env.py`'s `get_database_url()`, so the placeholder is never used directly.

- [ ] **Step 4: Generate the initial migration**

```bash
cd services/api
.local/dev/.venv/Scripts/alembic.exe revision --autogenerate -m "initial schema"
```

Expected: creates `alembic/versions/<hash>_initial_schema.py`.

- [ ] **Step 5: Review generated migration**

Open the generated file. Confirm it includes `CREATE TABLE` statements for all four tables and the three indexes. The auto-generated migration may use `sa.Column` syntax. Verify the `BIGINT GENERATED ALWAYS AS IDENTITY` pattern is reflected (SQLAlchemy uses `autoincrement=True` on BigInteger which generates this in Postgres). Verify CHECK constraint on `sessions.status` is present.

If the `JSONB` column type is missing (SQLAlchemy may fall back to `JSON`), manually edit the migration to use `postgresql.JSONB`:

```python
from sqlalchemy.dialects import postgresql
# Change:
sa.Column('payload', sa.JSON(), ...),
# To:
sa.Column('payload', postgresql.JSONB(), ...),
```

- [ ] **Step 6: Commit**

```bash
git add services/api/alembic/ services/api/alembic.ini
git commit -m "feat: add Alembic with initial Postgres schema migration"
```

---

### Task 3: Replace `DocAgentState` JSON implementation with SQLAlchemy

**Files:**
- Modify: `services/api/docagent_api/state.py`

The class interface (`list_tasks`, `get_task`, `save_task`, `list_sessions`, `get_session`, `save_session`, `append_timeline_event`, `list_timeline_events`, `append_raw_runtime_event`, `list_raw_runtime_events`, `workspace_root`) is fully preserved. Only the implementation changes.

A new method `list_timeline_events_after(session_id, after_row_id)` is added for the SSE incremental query (Task 6).

- [ ] **Step 1: Write a failing test for `append_timeline_event` + `list_timeline_events`**

In `services/api/tests/test_state.py`, add (the `pg_state` fixture will be wired in Task 8):

```python
def test_append_and_list_timeline_events(pg_state):
    pg_state.save_task({"id": "t1", "doc_type_id": "prd", "brief": "b", "title": "T1",
                        "description": "", "workspace_root": "w/t1",
                        "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"})
    pg_state.save_session({"id": "s1", "task_id": "t1", "status": "pending",
                           "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"})
    pg_state.append_timeline_event("s1", {"id": "e1", "kind": "user_message", "summary": "hi",
                                          "actor": "user", "paths": [], "status": "done",
                                          "created_at": "2026-01-01T00:00:00Z"})
    events = pg_state.list_timeline_events("s1")
    assert len(events) == 1
    assert events[0]["id"] == "e1"


def test_list_timeline_events_after(pg_state):
    pg_state.save_task({"id": "t2", "doc_type_id": "prd", "brief": "b", "title": "T2",
                        "description": "", "workspace_root": "w/t2",
                        "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"})
    pg_state.save_session({"id": "s2", "task_id": "t2", "status": "pending",
                           "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"})
    for i in range(3):
        pg_state.append_timeline_event("s2", {"id": f"e{i}", "kind": "user_message", "summary": f"msg {i}",
                                               "actor": "user", "paths": [], "status": "done",
                                               "created_at": "2026-01-01T00:00:00Z"})
    rows = pg_state.list_timeline_events_after("s2", after_row_id=0)
    assert len(rows) == 3
    first_row_id = rows[0][0]
    later = pg_state.list_timeline_events_after("s2", after_row_id=first_row_id)
    assert len(later) == 2
```

- [ ] **Step 2: Rewrite `state.py`**

Replace the entire contents of `services/api/docagent_api/state.py`:

```python
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session as DbSession

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

    # ── raw runtime events ─────────────────────────────────────────────────────

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
        "workspace_root": "",  # derived from path; set by caller
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
```

- [ ] **Step 3: Verify import**

```bash
cd services/api
.local/dev/.venv/Scripts/python.exe -c "from docagent_api.state import DocAgentState; print('ok')"
```

Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add services/api/docagent_api/state.py
git commit -m "feat: replace DocAgentState JSON impl with SQLAlchemy Postgres backend"
```

---

### Task 4: Update `app.py` — use DB-backed state, remove forced session recovery

**Files:**
- Modify: `services/api/docagent_api/app.py`

`_recover_interrupted_sessions` forced in-flight sessions to `failed` on startup. With Celery, Celery's own task recovery handles in-flight jobs. Remove the forced recovery; instead log a warning if sessions are found in running states.

- [ ] **Step 1: Update `app.py`**

Replace `_recover_interrupted_sessions` with a passive warning function, and wire the `DATABASE_URL` env var:

```python
# In create_app(), replace the _recover_interrupted_sessions call:
_warn_interrupted_sessions(state)
```

Add at the bottom of `app.py`:

```python
def _warn_interrupted_sessions(state: DocAgentState) -> None:
    """Log a warning for sessions left in running states (Celery will recover them)."""
    import logging
    running_states = {
        RuntimeSessionState.RUNNING_CONTEXT.value,
        RuntimeSessionState.RUNNING_DRAFT.value,
        RuntimeSessionState.RUNNING_REVISION.value,
        RuntimeSessionState.RUNNING_CHAT.value,
        RuntimeSessionState.RUNNING_CHECKLIST.value,
        RuntimeSessionState.RUNNING_EXPORT.value,
    }
    logger = logging.getLogger(__name__)
    interrupted = [s for s in state.list_sessions() if s["status"] in running_states]
    if interrupted:
        ids = ", ".join(s["id"] for s in interrupted)
        logger.warning("Sessions left in running state (will be recovered by worker): %s", ids)
```

Also update `create_app()` to pass `DATABASE_URL` from env:

```python
from docagent_api.db import get_database_url

# In create_app(), change:
state = DocAgentState(state_root or state_root_from_env() or root / ".local" / "docagent")
# To:
state = DocAgentState(
    state_root or state_root_from_env() or root / ".local" / "docagent",
    database_url=os.environ.get("DATABASE_URL"),
)
```

- [ ] **Step 2: Verify the app starts with SQLite in-memory (for quick local test without Postgres)**

```bash
cd services/api
DATABASE_URL="sqlite:///./test_temp.db" .local/dev/.venv/Scripts/python.exe -c "
from docagent_api.app import create_app
app = create_app()
print('app created ok')
import os; os.remove('test_temp.db')
"
```

Expected: `app created ok`.

- [ ] **Step 3: Commit**

```bash
git add services/api/docagent_api/app.py
git commit -m "feat: remove forced session recovery; wire DATABASE_URL to DocAgentState"
```

---

### Task 5: Add Celery app and `run_session` worker task

**Files:**
- Create: `services/api/docagent_api/celery_app.py`
- Create: `services/api/docagent_api/worker_tasks.py`

- [ ] **Step 1: Write a failing test for the `run_session` task**

In `services/api/tests/test_worker_tasks.py` (create it):

```python
from unittest.mock import MagicMock, patch
import pytest
from docagent_api.worker_tasks import run_session


def test_run_session_calls_runtime_adapter(tmp_path):
    mock_state = MagicMock()
    mock_state.get_session.return_value = {"id": "s1", "task_id": "t1", "status": "pending"}
    mock_state.get_task.return_value = {"id": "t1", "doc_type_id": "prd", "brief": "b",
                                        "workspace_root": str(tmp_path)}
    mock_adapter = MagicMock()
    mock_adapter.send_message.return_value = MagicMock(
        session_id="s1", next_state=MagicMock(value="draft_ready"), events=[], raw_events=[]
    )

    with patch("docagent_api.worker_tasks._get_state", return_value=mock_state), \
         patch("docagent_api.worker_tasks._get_adapter", return_value=mock_adapter):
        run_session("s1", "send_message", {"message": "Hello"})

    mock_adapter.send_message.assert_called_once_with("s1", "Hello")
```

- [ ] **Step 2: Run test to confirm failure**

```bash
.local/dev/.venv/Scripts/python.exe -m pytest services/api/tests/test_worker_tasks.py -q
```

Expected: FAIL (`worker_tasks` module not found).

- [ ] **Step 3: Create `celery_app.py`**

```python
# services/api/docagent_api/celery_app.py
from __future__ import annotations

import os
from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery("docagent", broker=REDIS_URL)

celery_app.conf.update(
    # Use Redis as broker only; track session status via Postgres, not Celery results
    task_ignore_result=True,
    # Acknowledge task only after it completes (not on receipt)
    task_acks_late=True,
    # Requeue task if worker process dies mid-execution
    task_reject_on_worker_lost=True,
    # Tasks requeued if worker is silent longer than this (must exceed max session runtime)
    broker_transport_options={"visibility_timeout": 3600},
    # Import worker_tasks to register tasks
    imports=["docagent_api.worker_tasks"],
)
```

- [ ] **Step 4: Create `worker_tasks.py`**

```python
# services/api/docagent_api/worker_tasks.py
from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from docagent_api.celery_app import celery_app
from docagent_api.routes._shared import append_runtime_result, set_session_state
from docagent_contracts import RuntimeSessionState


def _get_state():
    from docagent_api.state import DocAgentState
    root = Path(os.environ.get("DOCAGENT_STATE_ROOT", ".local/docagent"))
    return DocAgentState(root, database_url=os.environ.get("DATABASE_URL"))


def _get_adapter():
    from docagent_api.runtime_factory import create_runtime_adapter
    return create_runtime_adapter()


@celery_app.task(bind=True, max_retries=0)
def run_session(self, session_id: str, operation_name: str, operation_kwargs: dict[str, Any]) -> None:
    """Execute a runtime operation for a session in the background worker."""
    state = _get_state()
    adapter = _get_adapter()
    session = state.get_session(session_id)
    if session is None:
        return

    try:
        method = getattr(adapter, operation_name)
        result = method(session_id, **operation_kwargs)
        task_id = session["task_id"]
        append_runtime_result(state, task_id, session_id, result)
        set_session_state(state, session, result.next_state)
    except Exception as exc:
        from docagent_api.routes._shared import manual_event
        from docagent_contracts import SemanticEventKind, TimelineActor, TimelineStatus
        from uuid import uuid4

        task_id = session["task_id"]
        failure = manual_event(
            task_id, session_id, f"runtime-failed-{uuid4().hex[:8]}",
            TimelineActor.SYSTEM, SemanticEventKind.ERROR,
            f"Runtime operation failed: {exc}", [],
            status=TimelineStatus.FAILED,
        )
        state.append_timeline_event(session_id, asdict(failure))
        previous = RuntimeSessionState(session["status"])
        set_session_state(state, session, previous)
```

- [ ] **Step 5: Run tests**

```bash
.local/dev/.venv/Scripts/python.exe -m pytest services/api/tests/test_worker_tasks.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/api/docagent_api/celery_app.py services/api/docagent_api/worker_tasks.py services/api/tests/test_worker_tasks.py
git commit -m "feat: add Celery app and run_session worker task"
```

---

### Task 6: Update `_shared.py` to queue via Celery; update SSE to incremental Postgres polling

**Files:**
- Modify: `services/api/docagent_api/routes/_shared.py`
- Modify: `services/api/docagent_api/routes/sessions.py`

- [ ] **Step 1: Update `start_background_runtime_operation` in `_shared.py`**

The function currently calls `runner.submit(session_id, worker)`. Change it to enqueue a Celery task instead, with the inline runner as fallback when `DOCAGENT_QUEUE=inline`.

Add after the existing imports in `_shared.py`:

```python
import os as _os
```

Replace the `start_background_runtime_operation` function body:

```python
def start_background_runtime_operation(
    state: DocAgentState,
    task_id: str,
    session: dict[str, Any],
    running_state: RuntimeSessionState,
    operation: Any,
    runner: BackgroundRuntimeRunner,
    previous_state_on_failure: RuntimeSessionState | None = None,
    transition_prepared: bool = False,
    # New: operation_name + kwargs for Celery dispatch
    operation_name: str | None = None,
    operation_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    previous_state = previous_state_on_failure or RuntimeSessionState(session["status"])
    if not transition_prepared:
        prepare_transition(state, session, running_state)

    use_celery = _os.environ.get("DOCAGENT_QUEUE", "inline") == "celery"

    if use_celery and operation_name is not None:
        from docagent_api.worker_tasks import run_session
        run_session.delay(session["id"], operation_name, operation_kwargs or {})
    else:
        def worker() -> None:
            try:
                result = operation()
            except Exception as exc:
                failure = manual_event(
                    task_id, session["id"], f"runtime-failed-{uuid4().hex[:8]}",
                    TimelineActor.SYSTEM, SemanticEventKind.ERROR,
                    f"Runtime operation failed: {exc}", [],
                    status=TimelineStatus.FAILED,
                )
                state.append_timeline_event(session["id"], asdict(failure))
                set_session_state(state, session, previous_state)
                return
            append_runtime_result(state, task_id, session["id"], result)
            set_session_state(state, session, result.next_state)

        runner.submit(session["id"], worker)

    return {"session_id": session["id"], "accepted": True, "status": running_state.value}
```

- [ ] **Step 2: Update the SSE endpoint in `sessions.py` to use incremental polling**

Locate the `stream_timeline_sse` function (around line 270 in sessions.py). Replace its `generate()` inner function:

```python
@router.get("/sessions/{session_id}/timeline/stream")
async def stream_timeline_sse(session_id: str, request: Request) -> StreamingResponse:
    if state.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")

    max_polls = int(os.environ.get("DOCAGENT_SSE_MAX_POLLS", "1500"))
    poll_interval = float(os.environ.get("DOCAGENT_SSE_POLL_INTERVAL", "0.2"))

    async def generate():
        import asyncio
        last_row_id = 0
        for _ in range(max_polls):
            if await request.is_disconnected():
                return
            new_rows = await asyncio.to_thread(
                state.list_timeline_events_after, session_id, last_row_id
            )
            for row_id, event in new_rows:
                yield f"data: {_json.dumps(event)}\n\n"
                last_row_id = row_id
            await asyncio.sleep(poll_interval)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 3: Run backend tests**

```bash
.local/dev/.venv/Scripts/python.exe -m pytest services/api/tests/test_api.py services/api/tests/test_sse.py -q
```

Expected: PASS. (Tests that relied on in-memory JSON state still pass because `DocAgentState` is instantiated fresh in each test with the test DB fixture from Task 8.)

- [ ] **Step 4: Commit**

```bash
git add services/api/docagent_api/routes/_shared.py services/api/docagent_api/routes/sessions.py
git commit -m "feat: queue background ops via Celery; update SSE to incremental Postgres polling"
```

---

### Task 7: Add migration script and Docker Compose

**Files:**
- Create: `services/api/docagent_api/migrate_from_files.py`
- Create: `docker-compose.yml`
- Create: `docker-compose.override.yml`
- Create: `.env.example`

- [ ] **Step 1: Create `migrate_from_files.py`**

```python
# services/api/docagent_api/migrate_from_files.py
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
            if args.dry_run:
                print(f"  [dry-run] INSERT task {task_id}")
            else:
                result = conn.execute(text("""
                    INSERT INTO tasks (id, doc_type_id, brief, title, description, created_at, updated_at)
                    VALUES (:id, :doc_type_id, :brief, :title, :description, :created_at, :updated_at)
                    ON CONFLICT (id) DO NOTHING
                """), {
                    "id": task["id"],
                    "doc_type_id": task.get("doc_type_id", ""),
                    "brief": task.get("brief", ""),
                    "title": task.get("title"),
                    "description": task.get("description"),
                    "created_at": task.get("created_at", ""),
                    "updated_at": task.get("updated_at", ""),
                })
                inserted["tasks"] += result.rowcount

        for session_id, session in sessions.items():
            if args.dry_run:
                print(f"  [dry-run] INSERT session {session_id}")
            else:
                result = conn.execute(text("""
                    INSERT INTO sessions (id, task_id, status, created_at, updated_at)
                    VALUES (:id, :task_id, :status, :created_at, :updated_at)
                    ON CONFLICT (id) DO NOTHING
                """), {
                    "id": session["id"],
                    "task_id": session["task_id"],
                    "status": session.get("status", "pending"),
                    "created_at": session.get("created_at", ""),
                    "updated_at": session.get("updated_at", ""),
                })
                inserted["sessions"] += result.rowcount

        for session_id, events in timeline_events.items():
            for event in events:
                if args.dry_run:
                    print(f"  [dry-run] INSERT timeline event {event.get('id')} for session {session_id}")
                else:
                    result = conn.execute(text("""
                        INSERT INTO timeline_events (session_id, event_type, payload)
                        SELECT :session_id, :event_type, :payload::jsonb
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

        if not args.dry_run:
            conn.commit()

    if args.dry_run:
        print("Dry run complete. No data written.")
    else:
        print(f"Migration complete: {inserted['tasks']} tasks, {inserted['sessions']} sessions, {inserted['events']} timeline events inserted.")


def _read_map(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create `docker-compose.yml`**

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: docagent
      POSTGRES_USER: docagent
      POSTGRES_PASSWORD: docagent
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U docagent"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  api:
    build:
      context: services/api
      dockerfile: Dockerfile
    env_file: .env
    environment:
      DATABASE_URL: postgresql+psycopg2://docagent:docagent@postgres:5432/docagent
      REDIS_URL: redis://redis:6379/0
    volumes:
      - workspace_data:/workspace
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    ports:
      - "8000:8000"

  worker:
    build:
      context: services/api
      dockerfile: Dockerfile
    command: celery -A docagent_api.celery_app worker --loglevel=info
    env_file: .env
    environment:
      DATABASE_URL: postgresql+psycopg2://docagent:docagent@postgres:5432/docagent
      REDIS_URL: redis://redis:6379/0
      DOCAGENT_QUEUE: celery
      DOCAGENT_STATE_ROOT: /workspace/state
    volumes:
      - workspace_data:/workspace
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  web:
    build:
      context: apps/web
      dockerfile: Dockerfile
    ports:
      - "5173:80"
    depends_on:
      - api

volumes:
  postgres_data:
  redis_data:
  workspace_data:
```

- [ ] **Step 3: Create `docker-compose.override.yml`**

```yaml
# docker-compose.override.yml — dev overrides: hot reload for api and worker
services:
  api:
    build: ~
    image: ~
    command: uvicorn docagent_api.app:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - ./services/api:/app
      - workspace_data:/workspace

  worker:
    build: ~
    image: ~
    volumes:
      - ./services/api:/app
      - workspace_data:/workspace

  web:
    build: ~
    image: ~
    command: npm run dev -- --host 0.0.0.0
    volumes:
      - ./apps/web:/app
```

- [ ] **Step 4: Create `.env.example`**

```bash
# .env.example — copy to .env and fill in values
DATABASE_URL=postgresql+psycopg2://docagent:docagent@localhost:5432/docagent
REDIS_URL=redis://localhost:6379/0
DOCAGENT_QUEUE=celery
DOCAGENT_STATE_ROOT=/workspace/state
VITE_API_BASE=http://localhost:8000
```

- [ ] **Step 5: Commit**

```bash
git add services/api/docagent_api/migrate_from_files.py docker-compose.yml docker-compose.override.yml .env.example
git commit -m "feat: add migration script and Docker Compose single-machine deployment"
```

---

### Task 8: Update test fixtures to use Postgres with transaction rollback

**Files:**
- Modify: `services/api/tests/conftest.py`
- Modify: `services/api/tests/test_state.py`
- Modify: `services/api/tests/test_api.py`

- [ ] **Step 1: Add `testcontainers` dependency**

```bash
cd services/api
.local/dev/.venv/Scripts/pip.exe install testcontainers[postgres]
```

Add to `requirements.txt`:
```
testcontainers[postgres]>=4.0
```

- [ ] **Step 2: Add Postgres fixtures to `conftest.py`**

In `services/api/tests/conftest.py`, add (preserving any existing fixtures):

```python
import pytest
from pathlib import Path
from sqlalchemy import create_engine, text
from testcontainers.postgres import PostgresContainer

from docagent_api.db import Base, create_db_engine, create_session_factory
from docagent_api.state import DocAgentState


@pytest.fixture(scope="session")
def postgres_container():
    """Start a Postgres container once per test session."""
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def pg_engine(postgres_container, tmp_path_factory):
    """Create SQLAlchemy engine pointing at the test container."""
    url = postgres_container.get_connection_url().replace("psycopg2", "psycopg2")
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def pg_connection(pg_engine):
    """Each test runs inside a transaction that is rolled back afterwards."""
    connection = pg_engine.connect()
    transaction = connection.begin()
    yield connection
    transaction.rollback()
    connection.close()


@pytest.fixture
def pg_state(pg_engine, tmp_path):
    """DocAgentState backed by the test Postgres container, isolated per test via savepoint."""
    url = str(pg_engine.url)
    # Use a fresh session factory per test; tables already exist
    state = DocAgentState.__new__(DocAgentState)
    state.root = tmp_path
    (tmp_path / "workspaces").mkdir(parents=True, exist_ok=True)
    state._engine = pg_engine
    state._Session = create_session_factory(pg_engine)

    yield state

    # Clean up inserted rows after each test
    with pg_engine.connect() as conn:
        conn.execute(text("DELETE FROM raw_runtime_events"))
        conn.execute(text("DELETE FROM timeline_events"))
        conn.execute(text("DELETE FROM sessions"))
        conn.execute(text("DELETE FROM tasks"))
        conn.commit()
```

- [ ] **Step 3: Wire `test_state.py` to use `pg_state`**

In `services/api/tests/test_state.py`, change the state fixture from the file-backed `DocAgentState` to `pg_state`:

Find any test that does:
```python
state = DocAgentState(tmp_path)
```

Replace with:
```python
# state provided by pg_state fixture
```

Update test signatures:
```python
def test_append_and_list_timeline_events(pg_state):
    ...
```

- [ ] **Step 4: Wire `test_api.py` to use DB-backed state**

In `services/api/tests/test_api.py`, find the `create_app()` call in the test client fixture. Pass the test Postgres URL:

```python
@pytest.fixture
def client(pg_engine, tmp_path):
    url = str(pg_engine.url)
    app = create_app(state_root=tmp_path, runtime_adapter=StreamingFakeAdapter())
    # Override DATABASE_URL for this test
    import os
    os.environ["DATABASE_URL"] = url
    with TestClient(app) as c:
        yield c
    os.environ.pop("DATABASE_URL", None)
```

- [ ] **Step 5: Run the full backend test suite**

```bash
.local/dev/.venv/Scripts/python.exe -m pytest services/api/tests/ -q
```

Expected: PASS. Tests that don't use Postgres (pure unit tests) should continue to pass unchanged.

- [ ] **Step 6: Commit**

```bash
git add services/api/tests/conftest.py services/api/tests/test_state.py services/api/tests/test_api.py services/api/requirements.txt
git commit -m "test: add testcontainers Postgres fixtures with per-test transaction rollback"
```

---

### Task 9: Full verification

**Files:** No code changes expected.

- [ ] **Step 1: Backend test suite**

```bash
.local/dev/.venv/Scripts/python.exe -m pytest -q
```

Expected: PASS.

- [ ] **Step 2: Frontend build (unchanged by this plan)**

```bash
cd apps/web
npm run build
```

Expected: PASS.

- [ ] **Step 3: Verify migration script with `--dry-run`**

```bash
DATABASE_URL="postgresql+psycopg2://docagent:docagent@localhost:5432/docagent" \
.local/dev/.venv/Scripts/python.exe -m docagent_api.migrate_from_files --dry-run
```

Expected: prints migration plan or "Nothing to migrate." No errors.

- [ ] **Step 4: Verify Celery app can be imported**

```bash
.local/dev/.venv/Scripts/python.exe -c "from docagent_api.celery_app import celery_app; print('broker:', celery_app.conf.broker_url)"
```

Expected: prints the Redis URL.

- [ ] **Step 5: Verify Docker Compose config is valid**

```bash
docker compose config --quiet
```

Expected: exits 0 (no YAML errors).

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "chore: final cleanup and verification for backend persistence migration"
```

---

## Self-Review

**Spec coverage:**
- Postgres tables with all columns: Task 1 (ORM models in db.py) ✓
- Indexes on `timeline_events(session_id, id)`, `sessions(task_id)`, `raw_runtime_events(session_id)`: Task 1 ✓
- `sessions.status` CHECK constraint: Task 1 ✓
- `updated_at` via SQLAlchemy `onupdate=func.now()`: Task 1 ✓
- `BIGINT GENERATED ALWAYS AS IDENTITY` via `autoincrement=True` on BigInteger: Task 1 ✓
- Alembic migrations: Task 2 ✓
- Connection pool config: Task 1 (pool_size, max_overflow, pool_timeout, pool_recycle) ✓
- `DocAgentState` interface preserved: Task 3 ✓
- `list_timeline_events_after` for SSE incremental query: Task 3 ✓
- Remove `_recover_interrupted_sessions`: Task 4 ✓
- Celery with `task_acks_late`, `task_reject_on_worker_lost`, `visibility_timeout`: Task 5 ✓
- `BackgroundRuntimeRunner` inline fallback via `DOCAGENT_QUEUE=inline`: Task 6 ✓
- SSE incremental `WHERE id > last_seen_id` via `asyncio.to_thread`: Task 6 ✓
- `migrate_from_files.py` idempotent with `--dry-run`: Task 7 ✓
- Docker Compose with all 5 services + named volumes: Task 7 ✓
- `workspace_data` volume for document files (not JSON state): Task 7 ✓
- Redis as broker only (no result backend): Task 5 ✓
- Worker `command:` override in Compose: Task 7 ✓
- `.env.example`: Task 7 ✓
- Postgres testcontainers with per-test cleanup: Task 8 ✓

**Placeholder scan:** None found. All steps contain actual code or commands.

**Type consistency:** `list_timeline_events_after(session_id, after_row_id)` returns `list[tuple[int, dict[str, Any]]]` — used correctly in both `state.py` (Task 3) and `sessions.py` SSE endpoint (Task 6). `run_session(session_id, operation_name, operation_kwargs)` signature used consistently in Tasks 5 and 6.
