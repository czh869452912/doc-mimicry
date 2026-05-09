# Bug Fix Pass 1: Review-Identified Issues

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all Critical and High issues (plus key Medium issues) discovered in the May 2026 code review, restoring correct Docker deployment, draft editing, conversation reload, SSE stability, and session state behavior.

**Architecture:** Fixes are organized by subsystem: Docker config → DB schema → frontend types → draft state → conversation pane → SSE → session guards → backend robustness → component polish. Each task is independently testable and safe to commit.

**Tech Stack:** FastAPI/Python (backend), React 19/TypeScript/Vite (frontend), Docker Compose, SQLAlchemy/Alembic, nginx

---

## Issues Addressed

| ID | Severity | Summary |
|----|----------|---------|
| C-1 | Critical | API container missing `DOCAGENT_STATE_ROOT` — worker and API write to different paths |
| C-2 | Critical | Web Docker bakes `127.0.0.1:8000` — non-functional from remote host |
| C-3 | Critical | `TimelineEventRow.created_at` is `Column(Text)` in ORM but `DateTime` in migration |
| C-4 | Critical | `build_prompt_bundle` raises unhandled `FileNotFoundError` leaving orphan session |
| H-1 | High | `onDraftChange` is a no-op — auto-save never fires, user edits silently lost |
| H-2 | High | `inputForReload` crashes with TypeError when `parentMessageId` is null |
| H-3 | High | `/start`, `/check`, `/export` slash commands refresh immediately after 202 response |
| H-4 | High | `reviseSelectedText` refreshes immediately after 202 response |
| H-5 | High | `queuedCommand` effect double-fires when `submitInput` identity changes mid-flight |
| H-6 | High | `IDLE→RUNNING_CHAT` transition leaves session with `draft_ready` but no draft |
| M-1 | Medium | `api` service missing `DOCAGENT_QUEUE: celery` — worker receives no tasks |
| M-2 | Medium | SSE reconnect leaks `EventSource` connections on every disconnect |
| M-3 | Medium | `TimelineEvent` TS type missing `session_id`, `task_id`, `raw_event_id` |
| M-4 | Medium | `LoopActionResult` missing `accepted`, `status`, `raw_event_count`; `sendMessage` uses ad-hoc type |
| M-5 | Medium | `approve_outline` writes `draft/outline.md` without `mkdir -p` |
| M-7 | Medium | Double-click on background ops can submit two concurrent workers for same session |
| M-8 | Medium | `DocAgentComposer` `query` state not cleared after submit — slash suggestion stays open |
| M-9 | Medium | `WorkspacePane` `initialOpenState` recalculated but `react-arborist` ignores updates |
| L-1 | Low | Hardcoded development defaults in workspace creation form |
| L-5 | Low | TopBar doesn't distinguish `await_outline_approval` from idle |

---

## Files Modified

| File | Action | Purpose |
|------|--------|---------|
| `docker-compose.yml` | Modify | Add env vars to `api` service |
| `apps/web/nginx.conf` | Create | nginx config with proxy + SPA routing |
| `apps/web/Dockerfile` | Modify | Accept `VITE_API_BASE` build arg, copy nginx.conf |
| `services/api/docagent_api/db.py` | Modify | Fix `Column(Text)` → `Column(DateTime(timezone=True))` |
| `apps/web/src/types.ts` | Modify | Add missing fields to `TimelineEvent`, `LoopActionResult` |
| `apps/web/src/api.ts` | Modify | Fix `sendMessage` return type |
| `apps/web/src/shell/AppShell.tsx` | Modify | Add local draft state; fix post-202 refresh in `reviseSelectedText` |
| `apps/web/src/shell/panes/ConversationPane.tsx` | Modify | Fix `inputForReload` crash; fix double-exec guard; update composer guard |
| `apps/web/src/shell/state/useTimeline.ts` | Modify | Fix SSE `EventSource` reconnect leak |
| `apps/web/src/shell/conversation/slashCommands.ts` | Modify | Remove immediate post-202 refreshes |
| `apps/web/src/shell/assistant/DocAgentComposer.tsx` | Modify | Clear `query` on submit |
| `apps/web/src/shell/panes/WorkspacePane.tsx` | Modify | Remove hardcoded form defaults; fix `initialOpenState` |
| `apps/web/src/shell/TopBar.tsx` | Modify | Add `"waiting"` status for outline approval |
| `services/api/docagent_api/routes/tasks.py` | Modify | Wrap `build_prompt_bundle` with error handling |
| `services/api/docagent_api/routes/sessions.py` | Modify | Add `mkdir -p` before outline write; add double-submit guard |
| `services/api/docagent_api/session_state.py` | Modify | Remove `RUNNING_CHAT` from `IDLE` allowed transitions |
| `services/api/docagent_api/routes/_shared.py` | Modify | Guard `start_background_runtime_operation` against concurrent submissions |

---

## Task 1: Docker Deployment Fixes (C-1, C-2, M-1, L-2)

**Files:**
- Modify: `docker-compose.yml`
- Create: `apps/web/nginx.conf`
- Modify: `apps/web/Dockerfile`

- [ ] **Step 1: Add missing env vars to `api` service in `docker-compose.yml`**

Replace the `api` service environment block so both `DOCAGENT_STATE_ROOT` and `DOCAGENT_QUEUE` are present:

```yaml
  api:
    build:
      context: .
      dockerfile: services/api/Dockerfile
    environment:
      DATABASE_URL: postgresql+psycopg2://docagent:docagent@postgres:5432/docagent
      REDIS_URL: redis://redis:6379/0
      DOCAGENT_STATE_ROOT: /workspace/state
      DOCAGENT_QUEUE: celery
    volumes:
      - workspace_data:/workspace
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    ports:
      - "8000:8000"
```

- [ ] **Step 2: Add build args to `web` service in `docker-compose.yml`**

Replace the `web` service so it passes `VITE_API_BASE` at build time:

```yaml
  web:
    build:
      context: .
      dockerfile: apps/web/Dockerfile
      args:
        VITE_API_BASE: /api
    ports:
      - "5173:80"
    depends_on:
      - api
```

- [ ] **Step 3: Create `apps/web/nginx.conf` with SPA routing and API proxy**

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Proxy API calls to the backend container
    location /api/ {
        proxy_pass http://api:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        # Required for SSE: disable buffering so events stream immediately
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
    }

    # SPA fallback: any unmatched path serves index.html
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

- [ ] **Step 4: Update `apps/web/Dockerfile` to accept the build arg and use custom nginx.conf**

Replace the entire Dockerfile:

```dockerfile
FROM node:22-alpine AS build

ARG VITE_API_BASE=http://127.0.0.1:8000
ENV VITE_API_BASE=$VITE_API_BASE

WORKDIR /app

COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci

COPY apps/web ./
RUN npm run build

FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
```

- [ ] **Step 5: Verify the compose config is valid**

```bash
docker compose config --quiet
```

Expected: no output (valid config). If errors appear, fix the YAML indentation.

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml apps/web/nginx.conf apps/web/Dockerfile
git commit -m "fix: docker deployment — api env vars, nginx proxy, SPA routing, VITE_API_BASE build arg"
```

---

## Task 2: Fix ORM Column Type Mismatch (C-3)

**Files:**
- Modify: `services/api/docagent_api/db.py` lines 77, 88

- [ ] **Step 1: Run failing scenario to confirm the bug**

The bug manifests as ORM/DB inconsistency. Verify by checking what `create_tables()` would create vs. the migration:

```bash
cd services/api
python -c "
from docagent_api.db import TimelineEventRow, RawRuntimeEventRow
te_col = TimelineEventRow.__table__.c.created_at
rre_col = RawRuntimeEventRow.__table__.c.created_at
print('TimelineEventRow.created_at type:', type(te_col.type).__name__)
print('RawRuntimeEventRow.created_at type:', type(rre_col.type).__name__)
"
```

Expected output before fix:
```
TimelineEventRow.created_at type: Text
RawRuntimeEventRow.created_at type: Text
```

- [ ] **Step 2: Fix `TimelineEventRow.created_at` in `db.py` line 77**

Change:
```python
    created_at = Column(Text, nullable=False, server_default=func.now())
```
To:
```python
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
```

- [ ] **Step 3: Fix `RawRuntimeEventRow.created_at` in `db.py` line 88**

Change:
```python
    created_at = Column(Text, nullable=False, server_default=func.now())
```
To:
```python
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
```

- [ ] **Step 4: Verify the type is now correct**

```bash
cd services/api
python -c "
from docagent_api.db import TimelineEventRow, RawRuntimeEventRow
te_col = TimelineEventRow.__table__.c.created_at
rre_col = RawRuntimeEventRow.__table__.c.created_at
print('TimelineEventRow.created_at type:', type(te_col.type).__name__)
print('RawRuntimeEventRow.created_at type:', type(rre_col.type).__name__)
"
```

Expected:
```
TimelineEventRow.created_at type: DateTime
RawRuntimeEventRow.created_at type: DateTime
```

- [ ] **Step 5: Run existing backend tests to confirm nothing broken**

```bash
cd services/api
python -m pytest tests/test_state.py tests/test_sse.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add services/api/docagent_api/db.py
git commit -m "fix: align ORM Column type with migration — DateTime(timezone=True) for created_at on timeline/raw event rows"
```

---

## Task 3: Fix Frontend Type Contracts (M-3, M-4)

**Files:**
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/api.ts`

- [ ] **Step 1: Update `TimelineEvent` in `types.ts` to add missing backend fields**

Replace the `TimelineEvent` interface:

```typescript
export interface TimelineEvent {
  id: string;
  session_id: string;
  task_id: string;
  actor: string;
  kind: string;
  raw_event_id: string | null;
  summary: string;
  paths: string[];
  status: string;
  created_at?: string;
}
```

- [ ] **Step 2: Update `LoopActionResult` in `types.ts` to match backend `LoopActionResponse`**

Replace the `LoopActionResult` interface:

```typescript
export interface LoopActionResult {
  session_id: string;
  next_state?: string | null;
  event_count?: number | null;
  raw_event_count?: number | null;
  paths?: string[] | null;
  artifact_path?: string | null;
  accepted?: boolean | null;
  status?: string | null;
}
```

- [ ] **Step 3: Fix `sendMessage` return type in `api.ts` to use `LoopActionResult`**

Change the `sendMessage` entry in `api.ts`:

```typescript
  sendMessage: (sessionId: string, message: string) =>
    request<LoopActionResult>(
      `/sessions/${sessionId}/messages?background=true`,
      {
        method: "POST",
        body: JSON.stringify({ message }),
      },
    ),
```

- [ ] **Step 4: Run TypeScript check**

```bash
cd apps/web
npx tsc --noEmit
```

Expected: no errors. If new errors appear, they reveal places that assumed the old type — fix them before proceeding.

- [ ] **Step 5: Run frontend unit tests**

```bash
cd apps/web
npx vitest run
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/types.ts apps/web/src/api.ts
git commit -m "fix: align TimelineEvent and LoopActionResult TS types with backend response models"
```

---

## Task 4: Fix Draft Editor State and Auto-save (H-1)

The root cause: `onDraftChange={() => {}}` in `AppShell.tsx` is a no-op. The `DraftTab`'s source editor fires `onChange` but the parent never captures it, so user edits are lost on the next query re-fetch. `useAutoSave` receives a stale `markdown` value and can never detect changes.

**Files:**
- Modify: `apps/web/src/shell/AppShell.tsx`

- [ ] **Step 1: Add local draft state to `AppShell`**

At the top of `AppShell()`, after the existing `useState` declarations, add:

```typescript
const [localDraft, setLocalDraft] = useState<string | null>(null);
```

- [ ] **Step 2: Clear `localDraft` when the active task changes**

Add a `useEffect` after the existing state declarations (before the `treeData` computation):

```typescript
const activeTaskId = workspaces.activeTask?.id;
useEffect(() => {
  setLocalDraft(null);
}, [activeTaskId]);
```

- [ ] **Step 3: Use `localDraft` as the authoritative draft value, falling back to server data**

Change line 35:
```typescript
const draft = draftQuery.data?.markdown ?? "";
```
To:
```typescript
const draft = localDraft ?? draftQuery.data?.markdown ?? "";
```

- [ ] **Step 4: Wire `onDraftChange` to update `localDraft`**

Change `AppShell.tsx` line 136:
```typescript
onDraftChange={() => {}}
```
To:
```typescript
onDraftChange={setLocalDraft}
```

- [ ] **Step 5: Verify auto-save now functions**

Open the source editor tab, type some text. The "last save · saving" indicator should appear, then change to "last save · saved" after ~800ms. If you switch tasks and come back, the editor should show the server-persisted version.

- [ ] **Step 6: Run frontend unit tests**

```bash
cd apps/web
npx vitest run
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/shell/AppShell.tsx
git commit -m "fix: wire onDraftChange to local state so user edits survive query re-fetches and auto-save fires"
```

---

## Task 5: Fix inputForReload Crash (H-2)

When `parentMessageId` is null (reloading the first message), `parentIndex` equals `events.length`, causing `events[parentIndex]` to be `undefined`. Accessing `.kind` on `undefined` throws a `TypeError` that crashes the Conversation pane.

**Files:**
- Modify: `apps/web/src/shell/panes/ConversationPane.tsx` (the `inputForReload` function at the bottom)

- [ ] **Step 1: Add the bounds check guard**

Change the `inputForReload` function at the bottom of `ConversationPane.tsx`:

```typescript
function inputForReload(events: TimelineEvent[], parentMessageId: string | null) {
  const parentIndex = parentMessageId
    ? events.findIndex((event) => event.id === parentMessageId)
    : events.length;
  // When parentMessageId is null, parentIndex === events.length (out of bounds — intentional)
  // When parentMessageId refers to a message not found, parentIndex === -1
  if (parentIndex >= 0 && parentIndex < events.length) {
    const parentEvent = events[parentIndex];
    if (parentEvent.kind === "user_message" && parentEvent.summary.trim()) return parentEvent.summary;
  }
  const endIndex = parentIndex >= 0 ? parentIndex : events.length;
  for (let index = endIndex - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (event.kind === "user_message" && event.summary.trim()) return event.summary;
  }
  return null;
}
```

- [ ] **Step 2: Run the tests**

```bash
cd apps/web
npx vitest run
```

Expected: all pass (including existing `useTimeline` and `ConversationPane` tests).

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/shell/panes/ConversationPane.tsx
git commit -m "fix: guard inputForReload against out-of-bounds access when parentMessageId is null"
```

---

## Task 6: Remove Post-202 Refresh Anti-pattern (H-3, H-4)

All background operations return HTTP 202 immediately. Calling `refreshTimeline()` and `refreshWorkspace()` right after gets empty results (worker hasn't run yet). The SSE connection already handles pushing updates when the worker completes. We need to let SSE do its job instead of pre-emptively refreshing.

**Files:**
- Modify: `apps/web/src/shell/conversation/slashCommands.ts`
- Modify: `apps/web/src/shell/AppShell.tsx`

- [ ] **Step 1: Remove immediate refreshes from `/start` and `/check` in `slashCommands.ts`**

For `/start` — show a status message; SSE will deliver the real updates:
```typescript
  if (command === "/start") {
    await api.startLoop(session.id);
    return { handled: true, message: "Outline loop starting…" };
  }
```

For `/check`:
```typescript
  if (command === "/check") {
    await api.runChecklist(session.id);
    return { handled: true, message: "Checklist running…" };
  }
```

For `/export` — background=true, so the artifact isn't ready yet; open it only after a workspace refresh that confirms it exists. Remove the immediate artifact open and let the user open it from the workspace tree when SSE notifies:
```typescript
  if (command === "/export") {
    await api.exportMarkdown(session.id);
    return { handled: true, message: "Export started. Open the artifact from the workspace tree when it appears." };
  }
```

- [ ] **Step 2: Remove immediate refreshes from `reviseSelectedText` in `AppShell.tsx`**

Replace the `reviseSelectedText` function:

```typescript
async function reviseSelectedText(selectedText: string) {
  if (!workspaces.activeSession) return;
  await api.reviseSelection(
    workspaces.activeSession.id,
    selectedText,
    "Please revise the selected passage while preserving its meaning.",
  );
  // SSE will push workspace/draft invalidation when the worker completes
}
```

- [ ] **Step 3: Run TypeScript check**

```bash
cd apps/web
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Verify behavior manually**

In the running app:
1. Type `/start` and press Enter — status line should read "Outline loop starting…"
2. Timeline should update as SSE events arrive (not immediately on command execution)

- [ ] **Step 5: Run unit tests**

```bash
cd apps/web
npx vitest run
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/shell/conversation/slashCommands.ts apps/web/src/shell/AppShell.tsx
git commit -m "fix: remove premature post-202 refreshes from slash commands and reviseSelectedText — let SSE drive updates"
```

---

## Task 7: Fix SSE EventSource Reconnect Leak (M-2)

The `connect()` function in `useTimeline.ts` discards the cleanup function returned by recursive calls. On every disconnect, a new `EventSource` is created but never closed when the effect is torn down, leaking HTTP connections.

**Files:**
- Modify: `apps/web/src/shell/state/useTimeline.ts`

- [ ] **Step 1: Replace `connect()` with a version that tracks the current source**

Replace the entire SSE `useEffect` (lines 62–148) with:

```typescript
  useEffect(() => {
    if (!sessionId) return;
    const currentSessionId = sessionId;
    const currentTaskId = taskId;
    let cancelled = false;
    let pollId: ReturnType<typeof window.setInterval> | undefined;
    let reconnectId: ReturnType<typeof window.setTimeout> | undefined;
    let backoffMs = SSE_BACKOFF_BASE_MS;
    let closeCurrentSource: (() => void) | undefined;

    function invalidateRelatedQueries(event: TimelineEvent) {
      if (event.paths.length > 0) {
        void queryClient.invalidateQueries({ queryKey: ["workspace", currentTaskId] });
        if (event.paths.some((p) => p.startsWith("draft/"))) {
          void queryClient.invalidateQueries({ queryKey: ["draft", currentTaskId] });
        }
      }
      if (
        event.kind === "session_status" ||
        event.kind === "error" ||
        event.actor === "system"
      ) {
        void queryClient.invalidateQueries({ queryKey: ["sessions", currentTaskId] });
      }
    }

    function startPolling() {
      pollId = window.setInterval(() => {
        void api
          .getTimeline(currentSessionId)
          .then((nextEvents) => {
            if (!cancelled) setEvents(replaceWithIdDedup(nextEvents));
          })
          .catch((caught) => {
            if (!cancelled)
              setError(caught instanceof Error ? caught.message : "Could not refresh timeline");
          });
      }, TIMELINE_POLL_INTERVAL_MS);
    }

    function connect() {
      // Close any previously opened source before creating a new one
      closeCurrentSource?.();
      closeCurrentSource = undefined;

      if (!("EventSource" in window)) {
        startPolling();
        return;
      }
      const source = new EventSource(streamTimelineUrl(currentSessionId));
      closeCurrentSource = () => source.close();

      source.onmessage = (ev: MessageEvent) => {
        if (cancelled) return;
        backoffMs = SSE_BACKOFF_BASE_MS;
        try {
          const event = JSON.parse(ev.data as string) as TimelineEvent;
          setEvents((prev) => mergeTimelineEvents(prev, [event]));
          invalidateRelatedQueries(event);
        } catch {
          // ignore unparseable keep-alive frames
        }
      };

      source.onerror = () => {
        closeCurrentSource?.();
        closeCurrentSource = undefined;
        if (cancelled) return;
        void api.getTimeline(currentSessionId).then((nextEvents) => {
          if (!cancelled) setEvents(replaceWithIdDedup(nextEvents));
        });
        reconnectId = window.setTimeout(() => {
          if (!cancelled) connect();
        }, backoffMs);
        backoffMs = Math.min(backoffMs * 2, SSE_BACKOFF_MAX_MS);
      };
    }

    connect();

    return () => {
      cancelled = true;
      closeCurrentSource?.();
      if (pollId !== undefined) window.clearInterval(pollId);
      if (reconnectId !== undefined) window.clearTimeout(reconnectId);
    };
  }, [sessionId, taskId, queryClient]);
```

- [ ] **Step 2: Run existing SSE-related tests**

```bash
cd apps/web
npx vitest run src/shell/state/__tests__/useTimeline.test.tsx
```

Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/shell/state/useTimeline.ts
git commit -m "fix: close stale EventSource before reconnect to prevent SSE connection leak"
```

---

## Task 8: Fix queuedCommand Double-Execution (H-5)

When SSE delivers a session status update, `activeSession` changes → `ensureSession` changes → `submitInput` changes. The `useEffect` watching `[queuedCommand, submitInput, ...]` re-fires with the new `submitInput` while the original `queuedCommand` is still set, executing the command a second time.

**Files:**
- Modify: `apps/web/src/shell/panes/ConversationPane.tsx`

- [ ] **Step 1: Replace the queuedCommand effect with a one-shot guard**

Find the effect in `ConversationPane.tsx`:
```typescript
  useEffect(() => {
    if (!queuedCommand) return;
    void submitInput(queuedCommand).finally(() => {
      onQueuedCommandHandled?.();
    });
  }, [queuedCommand, submitInput, onQueuedCommandHandled]);
```

Replace it with:
```typescript
  const queuedCommandHandlingRef = useRef(false);
  useEffect(() => {
    if (!queuedCommand || queuedCommandHandlingRef.current) return;
    queuedCommandHandlingRef.current = true;
    void submitInput(queuedCommand).finally(() => {
      queuedCommandHandlingRef.current = false;
      onQueuedCommandHandled?.();
    });
    // Intentionally omit submitInput from deps — we only want to fire once per queuedCommand value.
    // submitInput identity changes on every session update (via ensureSession), but the command
    // itself is already captured in the closure at the time the effect first runs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queuedCommand, onQueuedCommandHandled]);
```

- [ ] **Step 2: Make sure `useRef` is already imported**

Check the top of `ConversationPane.tsx` — `useRef` should already be imported. The current file has:
```typescript
import { useCallback, useEffect, useRef, useState } from "react";
```
This is correct — no import change needed.

- [ ] **Step 3: Run tests**

```bash
cd apps/web
npx vitest run
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/shell/panes/ConversationPane.tsx
git commit -m "fix: prevent double-execution of queuedCommand when submitInput identity changes mid-flight"
```

---

## Task 9: Guard Against Chat on IDLE Sessions (H-6)

Sending a chat message to an `IDLE` session transitions it to `RUNNING_CHAT` and then `DRAFT_READY` — without ever generating a draft. This leaves the session permanently broken. Fix at both the state machine level (backend) and the UI level (frontend).

**Files:**
- Modify: `services/api/docagent_api/session_state.py`
- Modify: `apps/web/src/shell/panes/ConversationPane.tsx`

- [ ] **Step 1: Remove `RUNNING_CHAT` from `IDLE`'s allowed transitions in `session_state.py`**

Find `ALLOWED_TRANSITIONS` and change the `IDLE` entry from:
```python
    RuntimeSessionState.IDLE: {
        RuntimeSessionState.RUNNING_CONTEXT,
        RuntimeSessionState.RUNNING_REVISION,
        RuntimeSessionState.RUNNING_CHAT,
        RuntimeSessionState.CANCELLED,
    },
```
To:
```python
    RuntimeSessionState.IDLE: {
        RuntimeSessionState.RUNNING_CONTEXT,
        RuntimeSessionState.RUNNING_REVISION,
        RuntimeSessionState.CANCELLED,
    },
```

- [ ] **Step 2: Run backend session-state tests**

```bash
cd services/api
python -m pytest tests/test_session_state.py -v
```

Expected: all pass. If any test asserts that `IDLE→RUNNING_CHAT` is valid, update that test to assert it's now invalid.

- [ ] **Step 3: Update `canSubmitComposerInput` in `ConversationPane.tsx`**

Remove `"idle"` from the allowed set — an idle session needs `/start` first:

```typescript
function canSubmitComposerInput(activeSession: SessionRecord | null) {
  if (!activeSession) return true;  // no session yet — first message creates one via ensureSession
  return ["draft_ready", "paused", "failed"].includes(activeSession.status);
}
```

- [ ] **Step 4: Update `emptyMessage` to tell the user what to do when idle**

Change the `emptyMessage` function to provide clear guidance:

```typescript
function emptyMessage(activeTask: TaskRecord | null, activeSession: SessionRecord | null) {
  if (!activeTask) return "Create a workspace to begin.";
  if (!activeSession) return "Send a message to create a session, or type /start to begin the outline loop.";
  if (activeSession.status === "idle") return "Session is ready. Type /start to begin the outline loop.";
  if (activeSession.status === "await_outline_approval") return "Review and approve the outline above to continue.";
  if (activeSession.status === "completed") return "Session complete. Create a new session to start again.";
  if (activeSession.status === "cancelled") return "Session was cancelled. Create a new session to start again.";
  return null;
}
```

- [ ] **Step 5: Run frontend tests**

```bash
cd apps/web
npx vitest run
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add services/api/docagent_api/session_state.py apps/web/src/shell/panes/ConversationPane.tsx
git commit -m "fix: remove IDLE→RUNNING_CHAT transition; block composer input on idle sessions with guidance message"
```

---

## Task 10: Backend Robustness (C-4, M-5, M-7)

Three backend robustness gaps: (1) `create_session` leaves an orphaned session row if `build_prompt_bundle` fails, (2) `approve_outline` writes to `draft/outline.md` without ensuring the directory exists, (3) concurrent background submissions for the same session cause state corruption.

**Files:**
- Modify: `services/api/docagent_api/routes/tasks.py`
- Modify: `services/api/docagent_api/routes/sessions.py`
- Modify: `services/api/docagent_api/routes/_shared.py`

- [ ] **Step 1: Wrap `build_prompt_bundle` in `create_session` with error handling (`tasks.py`)**

Replace the `create_session` route function body from the `state.save_session(record)` line:

```python
    @router.post("/tasks/{task_id}/sessions", response_model=SessionResponse)
    def create_session(task_id: str) -> dict[str, Any]:
        task = require_task(state, task_id)
        session_id = f"session-{uuid4().hex[:8]}"
        created_at = utc_now()
        record = {
            "id": session_id,
            "task_id": task_id,
            "status": "idle",
            "created_at": created_at,
            "updated_at": created_at,
        }
        state.save_session(record)
        try:
            prompt_bundle = build_prompt_bundle(
                root,
                Path(task["workspace_root"]),
                task["id"],
                session_id,
                task["doc_type_id"],
            )
        except FileNotFoundError as exc:
            state.delete_session(session_id)
            raise HTTPException(
                status_code=422,
                detail=f"Cannot create session: missing skill or system prompt file — {exc}",
            ) from exc
        result = adapter.create_session(session_id, prompt_bundle)
        append_runtime_result(state, task["id"], session_id, result)
        return record
```

> **Note:** This requires `state.delete_session(session_id)` to exist. Check `DocAgentState` — if it doesn't exist, add it in the next step.

- [ ] **Step 2: Add `delete_session` method to `DocAgentState` if missing**

Open `services/api/docagent_api/state.py`. Check if `delete_session` exists. If not, add after `save_session`:

```python
    def delete_session(self, session_id: str) -> None:
        with self._db_session() as db:
            row = db.query(SessionRow).filter(SessionRow.id == session_id).first()
            if row:
                db.delete(row)
                db.commit()
```

- [ ] **Step 3: Add `mkdir -p` before outline write in `sessions.py` (`approve_outline`)**

Find line 90 in `sessions.py`:
```python
        (Path(task["workspace_root"]) / "draft" / "outline.md").write_text(outline_text, encoding="utf-8")
```

Replace with:
```python
        outline_path = Path(task["workspace_root"]) / "draft" / "outline.md"
        outline_path.parent.mkdir(parents=True, exist_ok=True)
        outline_path.write_text(outline_text, encoding="utf-8")
```

- [ ] **Step 4: Add double-submission guard to `start_background_runtime_operation` in `_shared.py`**

Find the `start_background_runtime_operation` function. At the start of the function body, add a guard that checks if a worker is already running for this session:

```python
def start_background_runtime_operation(
    state: DocAgentState,
    task_id: str,
    session: dict[str, Any],
    next_state: RuntimeSessionState,
    operation: Any,
    runner: BackgroundRuntimeRunner,
    *,
    previous_state_on_failure: RuntimeSessionState | None = None,
    transition_prepared: bool = False,
    operation_name: str = "operation",
    operation_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    session_id = session["id"]
    # Guard against concurrent background submissions for the same session
    if runner.is_running(session_id):
        raise HTTPException(
            status_code=409,
            detail=f"A background operation is already running for session {session_id}",
        )
    # ... rest of existing function body unchanged ...
```

> **Note:** Check if `BackgroundRuntimeRunner` has an `is_running(session_id)` method. If not, add it in the next step.

- [ ] **Step 5: Add `is_running` to `BackgroundRuntimeRunner` if missing**

Open `services/api/docagent_api/background.py`. Check if `is_running` exists. If not, add:

```python
    def is_running(self, session_id: str) -> bool:
        with self._lock:
            future = self._running.get(session_id)
            return future is not None and not future.done()
```

- [ ] **Step 6: Run backend tests**

```bash
cd services/api
python -m pytest tests/ -v -x
```

Expected: all pass. If `delete_session` or `is_running` tests need updating, fix them.

- [ ] **Step 7: Commit**

```bash
git add services/api/docagent_api/routes/tasks.py \
        services/api/docagent_api/routes/sessions.py \
        services/api/docagent_api/routes/_shared.py \
        services/api/docagent_api/state.py \
        services/api/docagent_api/background.py
git commit -m "fix: cleanup orphaned session on prompt build failure; mkdir before outline write; guard concurrent background ops"
```

---

## Task 11: Component and UX Polish (M-8, M-9, L-1, L-5)

**Files:**
- Modify: `apps/web/src/shell/assistant/DocAgentComposer.tsx`
- Modify: `apps/web/src/shell/panes/WorkspacePane.tsx`
- Modify: `apps/web/src/shell/TopBar.tsx`
- Modify: `apps/web/src/shell/AppShell.tsx`

### 11a: Clear `query` in `DocAgentComposer` after submit (M-8)

- [ ] **Step 1: Add click handler to the Send button that resets `query`**

In `DocAgentComposer.tsx`, wrap the `ComposerPrimitive.Send` with an `onClick` that clears `query`:

```tsx
      <ComposerPrimitive.Send
        className="aui-send-button"
        disabled={disabled}
        onClick={() => setQuery("")}
      >
        <Send size={15} />
      </ComposerPrimitive.Send>
```

### 11b: Fix `WorkspacePane` — remove hardcoded defaults, fix `initialOpenState` (M-9, L-1)

- [ ] **Step 2: Remove hardcoded `defaultValues` from the workspace form**

In `WorkspacePane.tsx`, change the `useForm` call:

```typescript
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<z.infer<typeof createWorkspaceSchema>>({
    resolver: zodResolver(createWorkspaceSchema),
    defaultValues: {
      title: "",
      description: "",
    },
  });
```

- [ ] **Step 3: Fix `initialOpenState` — compute it only once on mount, not on every `nodes` change**

Change line 58 from:
```typescript
  const initialOpenState = useMemo(() => Object.fromEntries(nodes.map((node) => [node.id, true])), [nodes]);
```
To:
```typescript
  // react-arborist only reads initialOpenState on first mount — recomputing on every
  // nodes change is wasteful and has no effect after the initial render.
  const initialOpenState = useMemo(() => Object.fromEntries(nodes.map((node) => [node.id, true])), []); // eslint-disable-line react-hooks/exhaustive-deps
```

### 11c: Extend TopBar status to show `"waiting"` for outline approval (L-5)

- [ ] **Step 4: Add `"waiting"` to `TopBar` status type**

In `TopBar.tsx`, update the `status` prop type:

```typescript
interface TopBarProps {
  workspaceLabel: string;
  sessionLabel: string;
  status: "idle" | "running" | "failed" | "waiting";
  onOpenCommandPalette: () => void;
  onOpenSettings: () => void;
}
```

- [ ] **Step 5: Update `topBarStatus` mapping in `AppShell.tsx`**

Change the `topBarStatus` computation:

```typescript
  const topBarStatus = workspaces.activeSession?.status?.startsWith("running")
    ? "running"
    : workspaces.activeSession?.status === "failed"
      ? "failed"
      : workspaces.activeSession?.status === "await_outline_approval"
        ? "waiting"
        : "idle";
```

- [ ] **Step 6: Add `data-status="waiting"` CSS if not already handled**

Check `apps/web/src/index.css` (or wherever `.status-dot` is styled) for a `[data-status="waiting"]` rule. If missing, add it (amber/yellow color is a good choice for "needs attention"):

```css
.status-dot[data-status="waiting"] {
  background: #f59e0b; /* amber-400 */
}
```

- [ ] **Step 7: Run TypeScript check and tests**

```bash
cd apps/web
npx tsc --noEmit && npx vitest run
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add apps/web/src/shell/assistant/DocAgentComposer.tsx \
        apps/web/src/shell/panes/WorkspacePane.tsx \
        apps/web/src/shell/TopBar.tsx \
        apps/web/src/shell/AppShell.tsx
git commit -m "fix: clear composer query on submit; remove hardcoded form defaults; stable initialOpenState; topbar waiting status"
```

---

## Final Verification

- [ ] **Run full backend test suite**

```bash
cd services/api
python -m pytest tests/ -v
```

Expected: all pass.

- [ ] **Run full frontend test suite**

```bash
cd apps/web
npx vitest run
```

Expected: all pass.

- [ ] **Run TypeScript type check**

```bash
cd apps/web
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Verify Docker build produces correct image (optional but recommended)**

```bash
docker compose build --no-cache
docker compose up -d
# Confirm web is reachable and API calls proxy correctly
curl http://localhost:5173/api/doc-types
```

Expected: JSON list of doc types (not a network error or nginx 404).

---

## Self-Review Checklist

- [x] **C-1 covered:** Task 1 adds `DOCAGENT_STATE_ROOT` to api service
- [x] **C-2 covered:** Task 1 adds nginx proxy and build arg
- [x] **C-3 covered:** Task 2 fixes ORM column types
- [x] **C-4 covered:** Task 10 wraps `build_prompt_bundle` with cleanup
- [x] **H-1 covered:** Task 4 wires `localDraft` state
- [x] **H-2 covered:** Task 5 adds bounds check in `inputForReload`
- [x] **H-3/H-4 covered:** Task 6 removes premature refreshes
- [x] **H-5 covered:** Task 8 adds one-shot guard via ref
- [x] **H-6 covered:** Task 9 removes IDLE→RUNNING_CHAT, updates UI guard
- [x] **M-1 covered:** Task 1 adds `DOCAGENT_QUEUE` to api service
- [x] **M-2 covered:** Task 7 tracks `closeCurrentSource` across reconnects
- [x] **M-3/M-4 covered:** Task 3 updates TypeScript types
- [x] **M-5 covered:** Task 10 adds `mkdir -p` before outline write
- [x] **M-7 covered:** Task 10 adds `is_running` guard
- [x] **M-8 covered:** Task 11a clears query on submit
- [x] **M-9 covered:** Task 11b stabilizes `initialOpenState`
- [x] **L-1 covered:** Task 11b removes hardcoded defaults
- [x] **L-5 covered:** Task 11c adds `"waiting"` status
