# Design: State Governance + Backend Persistence

**Date:** 2026-05-08
**Status:** Approved (post-review revision)
**Phases:** Sequential — Phase 1 (State Governance) then Phase 2 (Backend Persistence)

---

## Background

The deep research report identified two root causes that most directly affect UX stability and production readiness:

1. `AppShell` uses interval polling and a manual `draftReloadToken` counter to trigger refresh, causing editor/timeline flash and unnecessary network traffic.
2. The backend stores all state in JSON files with full-read/full-write on every event append, and uses an in-process `ThreadPoolExecutor` for background jobs with no crash recovery.

These are addressed sequentially: state governance (frontend) first, then backend persistence (backend), so each phase is independently reviewable and the API contract stays stable across both.

---

## Phase 1: State Governance (TanStack Router + TanStack Query)

### Problem Detail

- `AppShell` lines 92–105: a 1.5s `setInterval` fires while a session is running, calling `refreshActiveWorkspace()` and incrementing `draftReloadToken`, causing the draft editor to flash blank before reloading.
- `useTimeline.loadTimeline` calls `setEvents([])` on line 22 before fetching, causing timeline flash on every reload.
- URL params are synced manually via a `useEffect` + `setSearchParams`, which can miss updates or cause stale-closure bugs.
- `useWorkspaces` bundles docTypes, tasks, sessions, and workspace tree into one monolith hook with a single loading/error state; any refresh triggers a cascade reload.

### Router Migration

Replace `react-router-dom`'s `useSearchParams` with TanStack Router typed search params.

- Define one root route with `validateSearch`:
  ```ts
  validateSearch: (s) => ({
    task: typeof s.task === 'string' ? s.task : undefined,
    session: typeof s.session === 'string' ? s.session : undefined,
  })
  ```
- `AppShell` reads params via `useSearch()`.
- Selection changes navigate with `useNavigate({ search: { task, session }, replace: true })`.
- No more manual `setSearchParams` in a `useEffect`.
- `App.tsx` / `main.tsx` switch from `BrowserRouter` to TanStack Router's `RouterProvider`.

### Query Migration

Add `QueryClientProvider` at the app root. Replace all imperative fetch logic with Query hooks:

| Old pattern | Query key | staleTime |
|---|---|---|
| `api.listDocTypes()` in `loadInitialState` | `['docTypes']` | `Infinity` (rarely changes) |
| `api.listTasks()` | `['tasks']` | 30s |
| `api.listTaskSessions(taskId)` | `['sessions', taskId]` | 10s |
| `api.getWorkspace(taskId)` | `['workspace', taskId]` | 10s |
| draft loading + `draftReloadToken` | `['draft', taskId]` | 10s |
| `api.getTimeline(sessionId)` initial load | local timeline stream state | n/a |

All server-state queries use `placeholderData: keepPreviousData`, where `keepPreviousData` is the function imported from `@tanstack/react-query` (TanStack Query v5 API — it is a function, not a string literal):

```ts
import { keepPreviousData } from '@tanstack/react-query'
// ...
useQuery({ queryKey: ['draft', taskId], queryFn: ..., placeholderData: keepPreviousData })
```

This shows stale data while the next fetch completes, eliminating blank flashes on task/session switching.

Timeline is the deliberate exception: `useTimeline` owns an ordered stream snapshot in local hook state because it merges initial REST fetches, SSE messages, reconnect catch-up fetches, and non-EventSource polling fallback into one monotonic event list. There is no separate `['timeline', sessionId]` Query consumer. SSE still invalidates the Query-managed workspace, draft, and session records based on event metadata.

### SSE-Driven Invalidation

The 1.5s interval effect in `AppShell` is removed entirely. Instead, the SSE event handler in `useTimeline` calls targeted `queryClient.invalidateQueries` on receiving events, based on the `paths: string[]` field of each `TimelineEvent`:

- Event with a path starting with `draft/` → `invalidateQueries({ queryKey: ['draft', taskId] })`
- Event with any non-empty paths → `invalidateQueries({ queryKey: ['workspace', taskId] })`
- Event whose `kind` indicates session status change → `invalidateQueries({ queryKey: ['sessions', taskId] })`

The exact `kind` values that signal a session status change are determined during implementation by inspecting the backend semantic event model.

### SSE Connection Management

Because interval polling is removed, the SSE connection becomes the sole mechanism for live invalidation. `useTimeline` must handle disconnects robustly:

- On `source.onerror`, close the source and reconnect with **exponential backoff** (starting at 1s, capped at 30s).
- On reconnect, **re-fetch the full timeline** via `queryClient.invalidateQueries({ queryKey: ['timeline', sessionId] })` to compensate for events missed during the disconnected window.
- If the browser lacks `EventSource` support (SSR or test environments), fall back to a 3s polling interval (increased from the current 1.5s since Query's `refetchInterval` also covers this).
- The existing `startPolling` fallback in `useTimeline` is retained as the fallback path but is only active when SSE is unavailable, not as a permanent background loop.

### useWorkspaces Decomposition

`useWorkspaces` is dissolved into:

- `useTasks()` — Query hook for `['tasks']`
- `useSessions(taskId)` — Query hook for `['sessions', taskId]`
- `useWorkspaceTree(taskId)` — Query hook for `['workspace', taskId]`
- `useDraft(taskId)` — Query hook for `['draft', taskId]`
- `useActiveWorkspace()` — thin coordinator that holds active task/session as local UI selection state (not server state), reads initial values from typed URL params, and exposes `selectTask` / `selectSession` that call `navigate` + trigger relevant query invalidations.

Mutations (`createWorkspace`, `createSession`, `ensureSession`) become `useMutation` hooks that invalidate `['tasks']` or `['sessions', taskId]` on success.

### Timeline Contract Fix

Add `created_at: string` (ISO 8601) to the `TimelineEvent` type and to the backend's timeline event response model. Events created before this field was added (e.g. existing JSON-backed events that lack the field) are handled with a fallback: the frontend treats a missing `created_at` as `undefined` and the assistant-ui runtime falls back to `new Date(0)` for those events only, so old data does not break the UI. Once Phase 2 is complete all new events will have real timestamps.

### Files Affected (Phase 1)

- `apps/web/package.json` — add `@tanstack/react-router`, `@tanstack/react-query`
- `apps/web/src/main.tsx` — switch to `RouterProvider`
- `apps/web/src/App.tsx` — define typed root route
- `apps/web/src/shell/AppShell.tsx` — remove interval polling, `draftReloadToken`, manual `setSearchParams`; use `useSearch`, `useNavigate`, `useDraft`, `useActiveWorkspace`
- `apps/web/src/shell/state/useWorkspaces.ts` — dissolve into individual Query hooks
- `apps/web/src/shell/state/useTimeline.ts` — add invalidation calls on SSE events; remove `setEvents([])` clear-before-load; add exponential backoff reconnect
- `apps/web/src/shell/state/useActiveWorkspace.ts` — new coordinator (replaces selection logic from `useWorkspaces`)
- `apps/web/src/types.ts` — add optional `created_at` to `TimelineEvent`
- `services/api/docagent_api/response_models.py` — add `created_at` to timeline event response model
- `apps/web/src/shell/__tests__/AppShell.test.tsx` — update to use `RouterProvider` test harness
- `apps/web/tests/workbench-shell.spec.ts` — update deep-link tests

---

## Phase 2: Backend Persistence (Postgres + Celery + Docker Compose)

### Problem Detail

- `append_timeline_event` (state.py:50–57): reads the full `timelines/{session_id}.json` array, appends one event, rewrites the entire file. Grows unbounded with session length.
- SSE endpoint polls `list_timeline_events()` every 0.2s, each call a full file read.
- `tasks.json` / `sessions.json`: full-read + full-write per mutation, guarded by a single `RLock`. Not crash-safe; concurrent multi-process writes would corrupt data.
- `BackgroundRuntimeRunner` uses `ThreadPoolExecutor`. In-flight jobs are lost on process restart; session status is force-set to `failed` on startup.

### Storage Layer

Replace `DocAgentState`'s JSON file implementation with SQLAlchemy sync (psycopg2 driver) backed by Postgres. The `DocAgentState` class interface is preserved — all callers (routes, runtime adapters) are untouched. Only the implementation changes.

**Tables:**

```sql
tasks (
  id          TEXT PRIMARY KEY,
  doc_type_id TEXT NOT NULL,
  brief       TEXT NOT NULL,
  title       TEXT,
  description TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
)

sessions (
  id       TEXT PRIMARY KEY,
  task_id  TEXT NOT NULL REFERENCES tasks(id),
  status   TEXT NOT NULL CHECK (status IN (
             'pending', 'running_outline', 'running_draft',
             'running_checklist', 'draft_ready', 'completed',
             'failed', 'cancelled'
           )),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
)

timeline_events (
  id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id),
  event_type TEXT NOT NULL,
  payload    JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)

raw_runtime_events (
  id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id),
  runtime    TEXT NOT NULL,
  payload    JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
```

**Indexes:**

```sql
CREATE INDEX idx_sessions_task_id        ON sessions(task_id);
CREATE INDEX idx_timeline_session_id     ON timeline_events(session_id, id);
CREATE INDEX idx_raw_events_session_id   ON raw_runtime_events(session_id);
```

The composite index on `timeline_events(session_id, id)` is critical for the SSE incremental query (`WHERE session_id = ? AND id > ?`), which runs every 0.2s per active session.

**`updated_at` maintenance:** Managed by SQLAlchemy's `onupdate=func.now()` on the column definition in the ORM model. No database triggers are used; the application layer is responsible for all updates through SQLAlchemy.

**`BIGINT GENERATED ALWAYS AS IDENTITY`** is used instead of `BIGSERIAL` (SQL standard, avoids sequence ownership edge cases in Postgres 10+).

Alembic manages all schema migrations in `services/api/alembic/`. Initial migration creates all tables and indexes.

### Connection Pool

`db.py` configures the SQLAlchemy sync engine with explicit pool settings suitable for a containerised single-machine deployment:

```python
create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
)
```

These values are overridable via env vars (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`) for tuning without code changes.

### SSE Improvement

The SSE endpoint switches from full-file polling to incremental Postgres polling:

```sql
SELECT * FROM timeline_events
WHERE session_id = :session_id AND id > :last_seen_id
ORDER BY id
```

This runs every 0.2s but reads only new rows since the last seen id — far cheaper than re-reading the whole file. The `idx_timeline_session_id` index ensures this is an index seek rather than a table scan. Redis pub/sub `NOTIFY` can be added later as an optimization to eliminate the polling latency entirely.

### Worker Queue

Replace `BackgroundRuntimeRunner` (ThreadPoolExecutor) with Celery + Redis broker.

- `services/api/docagent_api/celery_app.py` — Celery app, Redis as broker only (no result backend; job status is tracked via the `sessions` table, not Celery results).
- `services/api/docagent_api/worker_tasks.py` — `run_session` Celery task (wraps existing runtime adapter logic).
- API route enqueues: `run_session.delay(session_id)` instead of `runner.submit(session_id, worker)`.
- Worker process: `celery -A docagent_api.celery_app worker --loglevel=info`.
- `BackgroundRuntimeRunner` is kept as a dev-mode fallback (activated by `DOCAGENT_QUEUE=inline` env var) for running without Redis.

**Celery task recovery configuration.** Celery does not automatically recover in-flight tasks on worker crash by default. The following must be explicitly configured:

```python
app.conf.update(
    broker_transport_options={
        'visibility_timeout': 3600,   # seconds; tasks requeued if worker silent this long
    },
    task_acks_late=True,              # ack only after task completes, not on receipt
    task_reject_on_worker_lost=True,  # requeue if worker dies mid-task
)
```

With `task_acks_late=True` and `task_reject_on_worker_lost=True`, a task that was running when the worker process died will be requeued and picked up by another worker (or the same worker after restart). The `visibility_timeout` must be set longer than the longest expected session runtime.

### Docker Compose

Single-machine deployment with five services:

```yaml
services:
  web:
    # Vite dev server or nginx static

  api:
    # FastAPI (uvicorn)
    depends_on: [postgres, redis]
    environment:
      DATABASE_URL: postgresql+psycopg2://...
      REDIS_URL: redis://redis:6379/0

  worker:
    # Same image as api — command overridden to start Celery worker
    image: ${API_IMAGE}
    command: celery -A docagent_api.celery_app worker --loglevel=info
    depends_on: [postgres, redis]
    environment:
      DATABASE_URL: postgresql+psycopg2://...
      REDIS_URL: redis://redis:6379/0
    volumes:
      - workspace_data:/workspace

  postgres:
    image: postgres:16-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
  workspace_data:
```

**`workspace_data` volume** holds workspace files (uploaded inputs, drafts, artifacts, context files) that the runtime adapter reads and writes during a session. This is distinct from the database: Postgres stores metadata and event records; the volume stores the actual document files. Both `api` and `worker` must mount this volume because the worker runs the runtime adapter which reads/writes workspace files directly. The existing `.local/docagent/workspaces/` directory maps to this volume on migration.

`DATABASE_URL` and `REDIS_URL` are env vars. A `.env.example` is provided. A `docker-compose.override.yml` enables bind-mount hot reload for development.

### Test Database Strategy

Tests use a real Postgres instance (not SQLite — SQLite does not support `JSONB`, async drivers, or all Postgres constraint features). Two options are acceptable:

- **Preferred:** `pytest-asyncio` fixtures spin up a temporary Postgres via `testcontainers-python`. Each test module gets a fresh database; each test runs inside a transaction that is rolled back on teardown.
- **Acceptable for CI:** A fixed `TEST_DATABASE_URL` env var points to a pre-existing test database. Each test runs in a transaction rolled back after the test.

SQLite fallback (`test_state.py — update to use test Postgres or SQLite`) is removed from scope; the spec previously mentioned it in error.

### Migration Path

`python -m docagent_api.migrate_from_files` reads existing `.local/docagent/*.json` and `timelines/*.json` files and inserts them into Postgres, preserving all IDs.

The script is **idempotent**: it uses `INSERT … ON CONFLICT DO NOTHING` so re-running it after a partial failure is safe. It logs each entity written and reports a summary count at the end. A `--dry-run` flag prints what would be inserted without writing.

Dev setup becomes `docker compose up` instead of manually activating the venv.

### Files Affected (Phase 2)

- `services/api/docagent_api/state.py` — replace JSON implementation with SQLAlchemy sync
- `services/api/docagent_api/db.py` — new: SQLAlchemy sync engine + session factory + pool config
- `services/api/alembic/` — new: Alembic env + initial migration (tables + indexes)
- `services/api/docagent_api/celery_app.py` — new: Celery app with recovery config
- `services/api/docagent_api/worker_tasks.py` — new: `run_session` Celery task
- `services/api/docagent_api/background.py` — keep as `inline` fallback, disabled by default
- `services/api/docagent_api/routes/sessions.py` — enqueue via Celery instead of `runner.submit`
- `services/api/docagent_api/routes/timeline.py` — update SSE to use incremental Postgres query
- `services/api/docagent_api/migrate_from_files.py` — new: idempotent migration script
- `docker-compose.yml` — new
- `docker-compose.override.yml` — new: dev hot-reload overrides
- `.env.example` — new
- `services/api/tests/conftest.py` — update fixture to use Postgres (testcontainers or TEST_DATABASE_URL) with transaction rollback
- `services/api/tests/test_state.py` — update for DB-backed state
- `services/api/tests/test_api.py` — update fixture to use DB-backed state

---

## What This Does Not Cover

- Skill pack versioning and pack manifest (planned as a later phase)
- Skill creator as first-class UI surface (later phase)
- Binary file import, DOCX/PDF export (later phase)
- Multi-user auth and organization model (future K8s phase)
- Redis pub/sub NOTIFY for zero-latency SSE (can be added after Postgres migration)
