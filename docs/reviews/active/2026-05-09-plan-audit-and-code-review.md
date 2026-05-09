# Plan Audit & Code Review — 2026-05-09

> **Purpose:** Audit all currently active plan / pending execution documents against the live code, and surface implementation issues found in the process.
> **Scope:** All files under `docs/superpowers/plans/` and `docs/reviews/active/` as of `af98c29`.
> **Reviewer:** Claude (Opus 4.7, 1M context).

---

## TL;DR

- **Bug-fix work is real.** All 11 tasks of `2026-05-09-bugfix-review-pass-1.md` are committed (`f04cc7e` … `8326585`), plus two follow-up UX commits (`f7ff83f`, `af98c29`). However, the checkboxes inside the plan are still `[ ]` and the file lives under `plans/`. **Action: tick the boxes and move the plan to `docs/superpowers/completed/`.**
- **Earlier plans are also done.** `state-governance` and `backend-persistence` are fully `[x]` checked and verified against code; `runtime-streaming` and `review-followup-assistant-ui-background-runner` have `[ ]` checkboxes despite the implementation being committed and visible in the codebase. **Action: archive all four.**
- **Strategic review (`deep-research-report.md`) is mostly absorbed** — its top three recommendations (state governance, backend persistence, deep linking + real timestamps) are already shipped. It still has open recommendations (skill-pack versioning, binary import, multi-user model). **Action: move to `completed/` with a note pointing at the executed plans, and split the still-open items into a new strategic backlog if the user wants them tracked.**
- **Two high-severity correctness issues uncovered in code review** that the plans did not address:
  - **C-A** Celery worker creates a fresh `OpenHandsRuntimeAdapter` per task — every background operation rebuilds the OpenHands conversation, losing all prior turns.
  - **C-B** `worker_tasks._get_state()` instantiates a new `DocAgentState` per Celery invocation, allocating a new SQLAlchemy engine + connection pool every time and re-running `Base.metadata.create_all()`.
- **Several medium / low items** worth recording (see §3).

---

## 1. Plan Audit

The repo currently surfaces **5 plans** in `docs/superpowers/plans/` and **1 active review**. After verification:

### 1.1 `2026-05-09-bugfix-review-pass-1.md` — IMPLEMENTED, **ARCHIVE**

All 11 tasks have matching commits on `main`. Verified by reading the live code:

| Task | Plan claim | Code verified |
|---|---|---|
| 1 — Docker | `docker-compose.yml` env vars + `apps/web/nginx.conf` + `apps/web/Dockerfile` build arg | ✅ `docker-compose.yml:34–36` has `DOCAGENT_STATE_ROOT` + `DOCAGENT_QUEUE`; `web` service has `args: VITE_API_BASE: /api`; `nginx.conf` and `Dockerfile` match plan verbatim |
| 2 — ORM type | `Column(DateTime(timezone=True))` for `created_at` | ✅ `services/api/docagent_api/db.py:52,53,65,66,77,88` |
| 3 — TS types | `TimelineEvent` + `LoopActionResult` widened | ✅ `apps/web/src/types.ts:28–39, 69–78` |
| 4 — Local draft | `localDraft` state + reset on task change + fallback chain | ✅ `apps/web/src/shell/AppShell.tsx:26, 37–39, 41, 144` |
| 5 — `inputForReload` guard | bounds check before `parentEvent.kind` | ✅ `apps/web/src/shell/panes/ConversationPane.tsx:220–236` |
| 6 — No post-202 refresh | slash commands + `reviseSelectedText` no longer refresh | ✅ `apps/web/src/shell/conversation/slashCommands.ts:39–50`; `AppShell.tsx:178–186` (only call + comment) |
| 7 — SSE leak | `closeCurrentSource` ref tracks current EventSource | ✅ `apps/web/src/shell/state/useTimeline.ts:70, 105–143, 149` |
| 8 — Queued command | one-shot `queuedCommandHandlingRef` | ✅ `ConversationPane.tsx:135–144` |
| 9 — IDLE→RUNNING_CHAT | transition removed; `canSubmitComposerInput` updated | ✅ `services/api/docagent_api/session_state.py:11–15` (only `RUNNING_CONTEXT`, `RUNNING_REVISION`, `CANCELLED`); `ConversationPane.tsx:81–84` blocks free-form chat unless `draft_ready/paused/failed` |
| 10 — Backend robustness | `delete_session`, `mkdir parents`, `is_running` guard | ✅ `services/api/docagent_api/state.py:107–112`; `routes/sessions.py:90–92`; `routes/_shared.py:128–133`; `background.py:48–51` |
| 11 — UX polish | `setQuery("")` on send, stable `initialOpenState`, `"waiting"` topbar status | ✅ `DocAgentComposer.tsx:88`; `WorkspacePane.tsx:58–61`; `AppShell.tsx:52–58`; `TopBar.tsx` (visible via prop type) |

**Two follow-up commits** outside the plan further evolved the composer:
- `f7ff83f` (15:53) — persistent composer hint via `composerHintFor`.
- `af98c29` (16:14) — composer always active, stop button during run, hints for blocked states, shortcut moved to Ctrl+Shift+P.

> **Note:** the plan was committed (`c7fff3e` 15:43) **after** Tasks 1–11 were already on `main`. That is why the checkboxes in the plan file are empty — it was reconstructed retrospectively. Recommend ticking them all `[x]` and moving the file to `completed/`.

### 1.2 `2026-05-08-state-governance.md` — IMPLEMENTED, **ARCHIVE**

All 8 tasks already `[x]`. Spot-checked:
- TanStack Router + Query wired (`apps/web/src/App.tsx:1–34`, `main.tsx`).
- `useActiveWorkspace` coordinator with URL state + localStorage + mutations (`apps/web/src/shell/state/useActiveWorkspace.ts`).
- Query hooks for tasks/sessions/workspace/draft/docTypes exist.
- `useTimeline.ts` no longer clears events on session change.
- `created_at` plumbed end-to-end (DB row → `_with_created_at` → `TimelineEvent` → assistant-ui message).

**One deviation worth recording** (not a bug): the plan said `useTimeline` would be a Query and SSE would `invalidateQueries(["timeline", id])`. The shipped implementation keeps timeline as `useState` and SSE pushes events directly into local state; `invalidateQueries` is only used for `workspace`/`draft`/`sessions`. The code has a comment explaining this. It works but means timeline refetch after error/reconnect is hand-rolled instead of automatic via Query refetch — keep an eye on it if SSE catch-up logic ever needs to grow.

### 1.3 `2026-05-08-backend-persistence.md` — IMPLEMENTED, **ARCHIVE**

All 9 tasks already `[x]`. Spot-checked:
- `db.py`, `state.py` are SQLAlchemy-backed (no JSON files).
- Alembic initialized; `services/api/alembic/` exists.
- `celery_app.py` + `worker_tasks.py` present; `_shared.py` switches on `DOCAGENT_QUEUE=celery`.
- SSE uses `list_timeline_events_after` via `asyncio.to_thread` (`sessions.py:313–324`).
- `migrate_from_files.py` exists.
- `docker-compose.yml`, `docker-compose.override.yml`, `.env.example` present.
- `_warn_interrupted_sessions` replaced forced recovery (`app.py:66–82`).

### 1.4 `2026-05-07-runtime-streaming.md` — IMPLEMENTED, **ARCHIVE (with task-1 note)**

Checkboxes are `[ ]` but evidence in code:
- `RuntimeEventSink`, `StreamingRuntimeAdapter` exported (`packages/contracts/docagent_contracts/runtime.py:59, 91–119`).
- `start_background_runtime_operation` exists (`routes/_shared.py:116–171`).
- OpenHands client `send_message_stream` poll-bridge (`agent/runtime-adapters/openhands/docagent_openhands_runtime/client.py:69–103`).
- OpenHands adapter has `send_message_stream`, `start_loop_stream`, `approve_outline_stream`, `revise_selection_stream`, `run_checklist_stream`, `export_markdown_stream` and a shared `_stream_result` helper.
- Frontend `api.sendMessage` posts to `?background=true`; SSE drives the UI.
- Background mode for `start_loop`, `approve_outline`, `revise_selection`, `run_checklist`, `export_markdown` all wired in `routes/sessions.py`.

**Task 1 (RLock on `DocAgentState`) is moot** — the JSON-file backend has been replaced by Postgres, so concurrency is handled by the database transaction model rather than an in-process lock. Tick `[x]` with a note "superseded by backend-persistence plan".

### 1.5 `2026-05-08-review-followup-assistant-ui-background-runner.md` — IMPLEMENTED, **ARCHIVE**

Checkboxes are `[ ]`. Evidence:
- Task 1 — frontend deps installed (no review failures observed when reading `package-lock.json` references in plans).
- Task 2 — deep-link URL restoration via TanStack Router `validateSearch` and `useActiveWorkspace`. Verified in `useActiveWorkspace.ts:31–58`.
- Task 3 — assistant-ui boundary: `DocAgentThread`, `DocAgentComposer`, `useDocAgentAssistantRuntime`, slash-command primitives are all in `apps/web/src/shell/assistant/`. CSS token-bridge present in `assistant-ui.css`.
- Task 4 — `BackgroundRuntimeRunner` exists with `submit`, `running_session_ids`, `is_running`, `shutdown` (`services/api/docagent_api/background.py`). `start_background_runtime_operation` calls `runner.submit`. `create_sessions_router` takes the runner via DI.
- Task 5 — review tracking doc lives in `docs/reviews/completed/2026-05-07-project-review-assistant-ui-integration.md` (already moved to `completed/`).

The plan also included scope text — the part about *daemon thread removal* is fully done. No `Thread(target=...).start()` remains in `services/api/docagent_api/routes/`.

### 1.6 `docs/reviews/active/deep-research-report.md` — MOSTLY ABSORBED, **MOVE TO `completed/`**

This is a strategic analysis dated 2026-05-07-ish. Its key recommendations and status:

| Recommendation | Status |
|---|---|
| First do "state governance" before any visual work | ✅ done (state-governance plan) |
| Replace JSON state + ThreadPool with Postgres + Celery | ✅ done (backend-persistence plan) |
| Add `created_at`, real timestamps on timeline events | ✅ done |
| Keep assistant-ui as central | ✅ done |
| Adopt TanStack Router + Query | ✅ done |
| Skill pack as versioned product object with `doc_type_version_id` pinning | ❌ not started |
| Binary import + conversion-report visualization | ❌ not started |
| DOCX/PDF export, multiple export engines | ❌ not started |
| Multi-user data model (`organization → doc_type → version → workspace …`) | ❌ not started |
| Move skill-creator out of SettingsDrawer into a first-class surface | ❌ not started |
| Stricter CI (frontend unit + Playwright as gates) | ❌ not started |

**Action:** archive this report to `completed/` (its assigned work has been planned and executed) **and** open a new short backlog file `docs/reviews/active/2026-05-09-strategic-followups.md` listing the unimplemented recommendations, so they don't get lost.

---

## 2. PLANS.md vs. Reality

`PLANS.md` says active plans live in `docs/exec-plans/active/` and completed in `docs/exec-plans/completed/`. The actual layout uses **two parallel trees**:

```
docs/exec-plans/completed/        ← phase plans (foundation, openhands, shell redesign, …)
docs/superpowers/plans/           ← current active plans (the 5 reviewed above)
docs/superpowers/completed/       ← completed superpowers plans (3 files)
docs/superpowers/specs/           ← design specs
```

This duplication is harmless but confusing. **Recommend** updating `PLANS.md` to mention the `docs/superpowers/{plans,completed,specs}/` tree, or consolidate into one location.

---

## 3. Code Review Findings

Severity legend: **C** = critical (correctness/data loss), **H** = high (functional bug or major perf), **M** = medium, **L** = low / cleanup.

### C-A — Celery worker recreates OpenHands runtime adapter per task, losing conversation context

**File:** `services/api/docagent_api/worker_tasks.py:13–46, 63–69`
**Trigger:** `DOCAGENT_QUEUE=celery` (i.e. the production deployment topology).

```python
def _get_adapter():
    from docagent_api.runtime_factory import create_runtime_adapter
    return create_runtime_adapter()
...
@celery_app.task(...)
def run_session(self, session_id, operation_name, operation_kwargs, ...):
    state = _get_state()
    adapter = _get_adapter()         # ← fresh OpenHandsRuntimeAdapter every call
    session = state.get_session(session_id)
    ...
    _ensure_runtime_session(state, adapter, session)  # rebuilds runtime session
    method = getattr(adapter, operation_name)
    result = method(session_id, **operation_kwargs)
```

`OpenHandsRuntimeAdapter` keeps `self._runtime_session_ids: dict[str, str]` and `self._states` only **in memory**. A new instance on every Celery task means:

1. `adapter.get_state(session_id)` raises `KeyError` (`_states` is empty).
2. `_ensure_runtime_session` falls through, calls `build_prompt_bundle`, then `adapter.create_session(...)` — which calls `OpenHandsAgentServerClient.create_session`, opening a **new** Conversation on the OpenHands server.
3. The new conversation has none of the previous turns — every `send_message` is effectively the first message of a fresh agent.

**Effect:** With Celery enabled, the agent has no memory across messages within a session. This is the opposite of what a multi-turn document loop needs.

**Suggested fix:** persist the runtime session ID alongside the DocAgent session in Postgres (e.g. add a `runtime_session_id` column to `sessions`), and have the worker resume the existing OpenHands conversation by ID instead of rebuilding. The `OpenHandsAgentServerClient` currently looks up conversations from its own in-memory `_conversations` dict — it would need a "rehydrate by ID" path.

Until fixed, **`DOCAGENT_QUEUE=celery` should be considered unsafe for OpenHands runtime**. The mock runtime tolerates this because it carries no real state.

### C-B — DocAgentState rebuilt per Celery task; `create_tables` runs every time

**File:** `services/api/docagent_api/worker_tasks.py:13–17`, `services/api/docagent_api/state.py:31–37`

```python
def _get_state():
    from docagent_api.state import DocAgentState
    root = Path(os.environ.get("DOCAGENT_STATE_ROOT", ".local/docagent"))
    return DocAgentState(root, database_url=os.environ.get("DATABASE_URL"))
```

`DocAgentState.__init__` always calls `create_tables(self._engine)` (`Base.metadata.create_all(engine)`) and creates a fresh `create_engine(...)` with its own connection pool. Each Celery task therefore:
- Opens a new Postgres connection pool of size 5 + 10 overflow.
- Issues a `CREATE TABLE IF NOT EXISTS …` round-trip per table.
- Discards the engine when the task ends (no `engine.dispose()`).

Under any non-trivial throughput, this leaks connections and floods the DB with metadata queries. It also defeats Alembic — `create_all` shouldn't run in production at all; migrations should.

**Suggested fix:** module-level cached `Engine` and `sessionmaker` per worker process (use `functools.lru_cache` or a small singleton). Skip `create_tables` when running under Celery (rely on Alembic). Consider making `DocAgentState.__init__` not auto-create tables when given an existing `engine`/`session_factory`.

### H-A — Local draft can mask SSE-driven server updates indefinitely

**File:** `apps/web/src/shell/AppShell.tsx:26, 37–41, 144`

`localDraft` is reset only when `activeTaskId` changes:

```ts
const [localDraft, setLocalDraft] = useState<string | null>(null);
useEffect(() => { setLocalDraft(null); }, [activeTaskId]);
const draft = localDraft ?? draftQuery.data?.markdown ?? "";
```

If a worker writes to `draft/` while the user has an unsaved edit:
1. SSE invalidates `["draft", taskId]`.
2. `draftQuery.data?.markdown` updates with the new server text.
3. `draft` still resolves to `localDraft` because `localDraft` is non-null.
4. The user never sees the worker's update unless they explicitly switch tasks and back.

The user can also lose their unsaved typing if they switch tasks within the auto-save debounce window (≈800ms) — `setLocalDraft(null)` fires before `useAutoSave` flushes.

**Suggested fix:** clear `localDraft` once `useAutoSave` confirms the local edit is persisted (e.g. on `save success` callback). And/or merge strategy when server data differs from `localDraft`: if server text is newer than the last local edit, prompt or auto-merge. The simplest robust fix is: keep `localDraft` only while `useAutoSave` is in *dirty* state, then drop it.

### H-B — SSE in `sessions.py` polls `list_timeline_events_after` every 200 ms; per-connection thread

**File:** `services/api/docagent_api/routes/sessions.py:302–330`

```python
async def generate():
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
```

`max_polls` defaults to 1500, `poll_interval` to 0.2 s ⇒ each connection lives ≈ 5 minutes and runs 5 polls/sec. With N concurrent users you have `N × 5` Postgres queries/sec just to poll for events. The frontend reconnects on the 5-minute boundary (no error, just `EventSource` close), so this is okay for single-user dev but bad under load.

**Suggested fix:** push notifications via Postgres `LISTEN/NOTIFY` (the worker `NOTIFY`'s a channel after each `INSERT` on `timeline_events`; the SSE handler `LISTEN`s and only queries when notified). Alternatively, use Redis pub/sub since Redis is already in the stack. The current "incremental polling" is what the spec called for, but it should not be the long-term answer.

### H-C — `useActiveWorkspace` ref-based init can fire twice in StrictMode and auto-redirect away from `/`

**File:** `apps/web/src/shell/state/useActiveWorkspace.ts:46–58`

```ts
const initialized = useRef(false);
useEffect(() => {
  if (tasksQuery.isLoading || initialized.current) return;
  initialized.current = true;
  if (!search.task && tasks.length > 0) {
    const remembered = window.localStorage.getItem(LAST_TASK_KEY);
    const task = tasks.find((t) => t.id === remembered) ?? latestByUpdatedAt(tasks);
    if (task) {
      void navigate({ search: { task: task.id }, replace: true });
    }
  }
}, [tasksQuery.isLoading, tasks, search.task, navigate]);
```

Two concerns:
1. In React 19 StrictMode, effects run mount→cleanup→mount on every dev render. The `useRef(false)` is preserved across these calls, so this part is OK *for the same component instance*. If the component remounts (e.g. router transitions), the ref re-initializes — fine in this case but worth knowing.
2. The `if (!search.task && tasks.length > 0)` branch unconditionally redirects away from `/`. This means a user landing on `/` (no params) is bounced to `/?task=…` and never sees an "empty"/landing experience. This is intentional per the spec but worth surfacing in case the desired UX is "stay on /, show task picker".

**Suggested fix:** none required if the redirect is desired. Document the behavior. If you want a landing page, branch on `tasks.length === 0` to show a welcome state and only redirect when the user explicitly selects a task.

### M-A — `worker_tasks.run_session` swallows `Exception` after using a possibly-stale `previous_state_on_failure`

**File:** `services/api/docagent_api/worker_tasks.py:70–86`

```python
except Exception as exc:
    ...
    rollback = RuntimeSessionState(previous_state_on_failure or session["status"])
    set_session_state(state, session, rollback)
```

`session["status"]` is the value loaded **before** the worker started. By the time the exception fires, the dispatcher has already called `prepare_transition` to advance the DB session into `running_*`. So `session["status"]` here is the OLD status (correct fallback). But this only works because the dispatcher mutates the in-memory `session` dict before passing it. If a future refactor reloads the session from DB inside the worker, the rollback target will be wrong. **Add a comment** or, better, always pass `previous_state_on_failure` from the dispatcher (it currently does, in `_shared.py:146`).

### M-B — `send_message` background path always appends user_event, sync path conditionally

**File:** `services/api/docagent_api/routes/sessions.py:230–276`

Background mode always inserts a manual `user_message` event (line 240–244). Sync mode inserts one only if `result.events` is empty (line 269–274). The asymmetry is intentional (the streaming runtime won't synthesize a user-message event for us), but it means a runtime that *does* emit a user-message event in its stream would produce a duplicate. None of the current adapters do this, but a comment explaining the contract would help.

### M-C — `useTimeline` re-fetches on session change *and* on every `taskId` change

**File:** `apps/web/src/shell/state/useTimeline.ts:53–59, 153`

```ts
useEffect(() => { ... loadTimeline(sessionId, ...) }, [loadTimeline, sessionId]);
// SSE effect:
useEffect(() => { ... }, [sessionId, taskId, queryClient]);
```

`taskId` is in the SSE deps but not the load deps. If `taskId` changes while `sessionId` doesn't (rare — a session belongs to exactly one task), the SSE effect tears down and reconnects but the loaded events stay. Probably fine. If `sessionId` changes while events are mid-loading, the previous `loadTimeline` call's `shouldApply()` correctly drops the stale result. OK.

### M-D — `DocAgentComposer` `useEffect` has unstable `aui` and `onDraftTextApplied` deps

**File:** `apps/web/src/shell/assistant/DocAgentComposer.tsx:25–31`

```ts
useEffect(() => {
  if (!draftText) return;
  aui.composer().setText(draftText);
  inputRef.current?.focus();
  setQuery(draftText);
  onDraftTextApplied?.();
}, [aui, draftText, onDraftTextApplied]);
```

`aui` from `useAui()` is stable per assistant runtime instance. `onDraftTextApplied` is `() => setQueuedComposerDraft(null)` from `AppShell` — recreated on every AppShell render. So the effect runs whenever AppShell re-renders, but is gated by `if (!draftText) return;` so the side-effects are no-ops. Functionally fine but wasteful. Wrap `onDraftTextApplied` in `useCallback` in AppShell to settle.

### L-A — `WorkspacePane` form `defaultValues: { title: "", description: "" }` is still present

The bugfix-pass-1 plan Step 11b said to "remove hardcoded form defaults". Empty strings are not hardcoded development defaults; they're necessary for `react-hook-form`'s controlled-input handling. The original L-1 issue was probably about non-empty defaults like a placeholder workspace title. The current state is correct; the plan wording was ambiguous. No action needed.

### L-B — `PLANS.md` references a directory that's not used anymore

`PLANS.md` says `docs/exec-plans/active/`, but active plans live under `docs/superpowers/plans/`. Update or consolidate.

### L-C — `_get_adapter` in worker module imports the factory inside the function

**File:** `services/api/docagent_api/worker_tasks.py:19–21`

Pulled inside the function to avoid circular imports — fine. A comment would help future readers. Same for `_get_state`.

### L-D — `SettingsDrawer` still hosts the Skill-Creator placeholder

The deep-research-report calls this out as a product-edge issue ("skill-creator must be a first-class surface, not a settings tab"). Not a code bug; a backlog item.

---

## 4. Recommended Actions

In priority order:

1. **Archive plans.** Move all 5 plan files from `docs/superpowers/plans/` to `docs/superpowers/completed/`. Tick remaining `[ ]` checkboxes (or add a `Status: completed on 2026-05-09` line at the top to avoid editing every checkbox).
2. **Move strategic review.** `docs/reviews/active/deep-research-report.md` → `docs/reviews/completed/`. Open a new `docs/reviews/active/2026-05-09-strategic-followups.md` capturing the un-implemented recommendations (skill-pack versioning, binary import, DOCX export, multi-user model, skill-creator surface, CI hardening).
3. **Fix C-A** (Celery + OpenHands conversation reuse). This is currently a silent-failure data path. Do this before declaring the Celery deployment usable.
4. **Fix C-B** (cache `DocAgentState` per worker process). Cheap to implement, removes connection-pool churn and accidental `create_all` calls.
5. **Patch H-A** so workers' draft updates are visible while a user has unsaved edits.
6. **Update `PLANS.md`** to reflect the actual `docs/superpowers/{plans,completed,specs}/` layout — or migrate everything into a single tree.
7. **Plan H-B** (Postgres `LISTEN/NOTIFY` or Redis pub/sub) before any multi-user load testing.
8. The remaining M / L items are good-citizen cleanups; bundle into a future polish pass.

---

## Appendix: Files inspected

Backend
- `services/api/docagent_api/db.py`, `state.py`, `app.py`, `session_state.py`, `background.py`, `worker_tasks.py`, `celery_app.py`
- `services/api/docagent_api/routes/_shared.py`, `routes/sessions.py`, `routes/tasks.py`
- `packages/contracts/docagent_contracts/runtime.py`
- `agent/runtime-adapters/openhands/docagent_openhands_runtime/{client.py,adapter.py}`

Frontend
- `apps/web/src/App.tsx`, `types.ts`
- `apps/web/src/shell/AppShell.tsx`, `panes/ConversationPane.tsx`, `panes/WorkspacePane.tsx`
- `apps/web/src/shell/state/{useTimeline.ts,useActiveWorkspace.ts}`
- `apps/web/src/shell/conversation/slashCommands.ts`
- `apps/web/src/shell/assistant/DocAgentComposer.tsx`

Infra / docs
- `docker-compose.yml`, `apps/web/Dockerfile`, `apps/web/nginx.conf`
- All 5 plans under `docs/superpowers/plans/`
- `docs/reviews/active/deep-research-report.md`
- `PLANS.md`
