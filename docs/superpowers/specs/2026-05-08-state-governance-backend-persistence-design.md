# Design: State Governance + Backend Persistence

**Date:** 2026-05-08
**Status:** Approved
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
| `api.getTimeline(sessionId)` initial load | `['timeline', sessionId]` | 5s |

All queries use `placeholderData: keepPreviousData` (TanStack Query v5 API) so switching tasks/sessions shows stale data rather than a blank flash while the next fetch completes.

### SSE-Driven Invalidation

The 1.5s interval effect in `AppShell` is removed. Instead, the SSE event handler in `useTimeline` calls targeted `queryClient.invalidateQueries` on receiving events, based on the `paths: string[]` field of each `TimelineEvent`:

- Any event → `invalidateQueries(['timeline', sessionId])`
- Event with a path starting with `draft/` → `invalidateQueries(['draft', taskId])`
- Event with any path → `invalidateQueries(['workspace', taskId])`
- Event with `kind === 'session_status'` (or any status-changing kind) → `invalidateQueries(['sessions', taskId])`

`useTimeline`'s role becomes: (a) deliver live incremental events to the timeline display via SSE merge, and (b) trigger Query cache invalidation. It no longer manages polling itself.

### useWorkspaces Decomposition

`useWorkspaces` is dissolved into:

- `useTasks()` — Query hook for `['tasks']`
- `useSessions(taskId)` — Query hook for `['sessions', taskId]`
- `useWorkspaceTree(taskId)` — Query hook for `['workspace', taskId]`
- `useDraft(taskId)` — Query hook for `['draft', taskId]`
- `useActiveWorkspace()` — thin coordinator that holds active task/session as local UI selection state (not server state), reads initial values from typed URL params, and exposes `selectTask` / `selectSession` that call `navigate` + trigger relevant query invalidations.

Mutations (`createWorkspace`, `createSession`, `ensureSession`) become `useMutation` hooks that invalidate `['tasks']` or `['sessions', taskId]` on success.

### Timeline Contract Fix

Add `created_at: string` (ISO 8601) to the `TimelineEvent` type and to the backend's timeline event schema. The assistant-ui runtime maps this to real `Date` objects instead of `new Date(0)`.

### Files Affected (Phase 1)

- `apps/web/package.json` — add `@tanstack/react-router`, `@tanstack/react-query`
- `apps/web/src/main.tsx` — switch to `RouterProvider`
- `apps/web/src/App.tsx` — define typed root route
- `apps/web/src/shell/AppShell.tsx` — remove interval polling, `draftReloadToken`, manual `setSearchParams`; use `useSearch`, `useNavigate`, `useDraft`, `useActiveWorkspace`
- `apps/web/src/shell/state/useWorkspaces.ts` — dissolve into individual Query hooks
- `apps/web/src/shell/state/useTimeline.ts` — add invalidation calls on SSE events; remove `setEvents([])` clear-before-load
- `apps/web/src/shell/state/useActiveWorkspace.ts` — new coordinator (replaces selection logic from `useWorkspaces`)
- `apps/web/src/types.ts` — add `created_at` to `TimelineEvent`
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

Replace `DocAgentState`'s JSON file implementation with SQLAlchemy async (asyncpg driver) backed by Postgres. The `DocAgentState` class interface is preserved — all callers (routes, runtime adapters) are untouched. Only the implementation changes.

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
  id          TEXT PRIMARY KEY,
  task_id     TEXT NOT NULL REFERENCES tasks(id),
  status      TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
)

timeline_events (
  id          BIGSERIAL PRIMARY KEY,
  session_id  TEXT NOT NULL REFERENCES sessions(id),
  event_type  TEXT NOT NULL,
  payload     JSONB NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
)

raw_runtime_events (
  id          BIGSERIAL PRIMARY KEY,
  session_id  TEXT NOT NULL REFERENCES sessions(id),
  runtime     TEXT NOT NULL,
  payload     JSONB NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
)
```

`append_timeline_event` becomes a single `INSERT INTO timeline_events`. `list_timeline_events` becomes `SELECT … WHERE session_id = ? ORDER BY id`. Both are O(1) for the write path.

Alembic manages migrations in `services/api/alembic/`.

### SSE Improvement

The SSE endpoint switches from full-file polling to incremental Postgres polling:

```sql
SELECT * FROM timeline_events
WHERE session_id = :session_id AND id > :last_seen_id
ORDER BY id
```

This runs every 0.2s but reads only new rows since the last seen id — far cheaper than re-reading the whole file. Redis pub/sub `NOTIFY` can be added later as an optimization to eliminate the 0.2s latency.

### Worker Queue

Replace `BackgroundRuntimeRunner` (ThreadPoolExecutor) with Celery + Redis.

- `services/api/docagent_api/celery_app.py` — Celery app with Redis broker + result backend
- `services/api/docagent_api/tasks.py` — `run_session` Celery task (wraps existing runtime adapter logic)
- API route enqueues: `run_session.delay(session_id)` instead of `runner.submit(session_id, worker)`
- Worker process: `celery -A docagent_api.celery_app worker --loglevel=info`
- On API restart, in-flight sessions that were `running_*` are recoverable via Celery task retry rather than forced to `failed`.
- `BackgroundRuntimeRunner` is kept as a dev-mode fallback (activated by `DOCAGENT_QUEUE=inline` env var) for running without Redis.

### Docker Compose

Single-machine deployment with five services:

```yaml
services:
  web:      # Vite dev server or nginx static
  api:      # FastAPI (uvicorn), depends_on: postgres, redis
  worker:   # Celery worker, same image as api, depends_on: postgres, redis
  postgres: # postgres:16-alpine
  redis:    # redis:7-alpine

volumes:
  postgres_data:
  redis_data:
  workspace_data:   # mounted into api and worker
```

`DATABASE_URL` and `REDIS_URL` are env vars. A `.env.example` is provided. A `docker-compose.override.yml` enables hot reload for development.

### Migration Path

A one-time `python -m docagent_api.migrate_from_files` script reads existing `.local/docagent/*.json` and `timelines/*.json` files and inserts them into Postgres, preserving all task/session/event IDs. Dev setup becomes `docker compose up` instead of manually activating the venv.

### Files Affected (Phase 2)

- `services/api/docagent_api/state.py` — replace JSON implementation with SQLAlchemy async
- `services/api/docagent_api/db.py` — new: SQLAlchemy engine + session factory
- `services/api/alembic/` — new: migration scripts
- `services/api/docagent_api/celery_app.py` — new: Celery app definition
- `services/api/docagent_api/tasks.py` — new: `run_session` Celery task
- `services/api/docagent_api/background.py` — keep as `inline` fallback, disable by default
- `services/api/docagent_api/routes/sessions.py` — enqueue via Celery instead of `runner.submit`
- `services/api/docagent_api/routes/timeline.py` — update SSE to use incremental Postgres query
- `services/api/docagent_api/migrate_from_files.py` — new: one-time migration script
- `docker-compose.yml` — new
- `docker-compose.override.yml` — new: dev hot-reload overrides
- `.env.example` — new
- `services/api/tests/test_state.py` — update to use test Postgres or SQLite (via env var)
- `services/api/tests/test_api.py` — update fixture to use DB-backed state

---

## What This Does Not Cover

- Skill pack versioning and pack manifest (planned as a later phase)
- Skill creator as first-class UI surface (later phase)
- Binary file import, DOCX/PDF export (later phase)
- Multi-user auth and organization model (future K8s phase)
- Redis pub/sub NOTIFY for zero-latency SSE (can be added after Postgres migration)
