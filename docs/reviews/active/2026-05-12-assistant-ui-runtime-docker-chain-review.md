# Assistant UI To Runtime Docker Chain Review

Date: 2026-05-12

Scope: assistant-ui frontend integration, frontend/backend interaction, agent runtime adapter handoff, Docker packaging, Docker runtime networking, and full run path.

## Review Findings

### Finding 1: OpenHands runtime selection is not passed into Docker Compose services

Severity: Critical

Evidence:

- `scripts/dev.ps1` sets `$env:DOCAGENT_RUNTIME = $Runtime` before running `docker compose up`.
- `docker-compose.yml` sets explicit `environment` blocks for `api` and `worker`, but neither includes `DOCAGENT_RUNTIME`.
- `docker-compose.override.yml` only adds `DOCAGENT_REPO_ROOT`.
- `services/api/docagent_api/runtime_factory.py` defaults to `mock` when `DOCAGENT_RUNTIME` is missing.

Impact:

Running `.\start-dev.cmd -Runtime openhands` can start or validate an OpenHands Agent Server on the host, but the API and worker containers still default to the mock adapter. The advertised OpenHands full-chain path is therefore not actually selected inside Docker.

Suggested fix:

Add `DOCAGENT_RUNTIME`, `OPENHANDS_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, and `LLM_BASE_URL` to the compose environment for both `api` and `worker`, using host environment interpolation or an env file. Add a smoke test that inspects `/sessions` behavior or container env to prove `-Runtime openhands` reaches the backend.

### Finding 2: Host OpenHands URL is not container-reachable when passed as 127.0.0.1

Severity: Critical

Evidence:

- `scripts/dev.ps1` defaults OpenHands to `http://127.0.0.1:$OpenHandsPort`.
- `README.md` documents OpenHands Agent Server at `http://127.0.0.1:8001`.
- `services/api/README.md` documents `OPENHANDS_BASE_URL = "http://127.0.0.1:8001"`.
- The API and worker run inside Docker containers.

Impact:

If `OPENHANDS_BASE_URL=http://127.0.0.1:8001` is eventually passed into the containers, `127.0.0.1` resolves to the API or worker container itself, not the Windows host where `scripts/dev.ps1` starts OpenHands. The API/worker cannot reach the OpenHands Agent Server, so the real runtime path fails at session creation.

Suggested fix:

For Docker Desktop development, translate host OpenHands URLs to `http://host.docker.internal:8001` before injecting them into compose, or run OpenHands as a compose service on the same Docker network and use a service name such as `http://openhands:8001`. Update README and `services/api/README.md` to distinguish host and container URLs.

### Finding 3: Celery worker cannot use API-created OpenHands sessions because adapter session bindings are process-local

Severity: Critical

Evidence:

- `OpenHandsRuntimeAdapter` stores `_runtime_session_ids` and `_states` in instance dictionaries.
- `create_session` is called by the API process in `services/api/docagent_api/routes/tasks.py`.
- Background Celery execution in `services/api/docagent_api/worker_tasks.py` creates a new adapter instance with `_get_adapter()`.
- `_ensure_runtime_session()` calls `adapter.get_state(session["id"])`; for a new OpenHands adapter instance this raises, then it creates a second runtime session in the worker process.

Impact:

The session visible to the API process is not the runtime session used by the worker. In OpenHands mode, follow-up operations can silently fork runtime context, lose conversation state, or operate against a different OpenHands conversation from the one created during session initialization. This breaks resume, chat continuity, and any assumption that the backend session id maps to one runtime session.

Suggested fix:

Persist the runtime session binding in product state, for example `session.runtime_session_id` plus runtime metadata, and make adapters stateless or reconstructable from persisted binding. The worker should load the existing runtime session id instead of creating a fresh conversation. Add an integration-style test that creates a session through one adapter instance and runs a background operation through another.

Implementation note: first verify whether the current OpenHands Agent Server/SDK can reconnect to an existing conversation id across processes. If it cannot, the product must choose an explicit fallback such as failing and clearing stale state, creating a new product session, or pinning OpenHands execution to the worker that created the runtime session. It must not silently create a second OpenHands conversation under the same product session id.

### Finding 4: API and worker can diverge on OpenHands configuration and LLM credentials

Severity: Critical

Evidence:

- `OpenHandsAgentServerClient.create_session()` requires `OPENHANDS_BASE_URL` and `LLM_API_KEY`, and reads `LLM_MODEL` and `LLM_BASE_URL`.
- `docker-compose.yml` does not pass any of these variables to `api` or `worker`.
- `scripts/dev.ps1` validates the variables in the host process only, then starts Docker Compose without injecting them.

Impact:

Even if `DOCAGENT_RUNTIME=openhands` were correctly set, containerized `create_session()` fails with missing `OPENHANDS_BASE_URL` or `LLM_API_KEY`. If only one service receives the variables later, API session creation and worker background operations will behave differently.

Suggested fix:

Centralize runtime env injection through `.env.local` or compose interpolation and apply it identically to `api` and `worker`. Add startup logging or `/health` diagnostics that show selected runtime and whether required runtime configuration is present without printing secret values.

### Finding 5: Running-state recovery is only logged, leaving interrupted sessions stuck

Severity: High

Evidence:

- `services/api/docagent_api/app.py` calls `_warn_interrupted_sessions(state)` on startup.
- `_warn_interrupted_sessions()` only logs a warning for sessions in running states.
- The comment says "Celery will recover them", but no recovery task is registered or invoked in `worker_tasks.py` or `celery_app.py`.
- `ConversationPane` blocks free-form sends unless status is `draft_ready`, `paused`, or `failed`.

Impact:

If API or worker restarts during `running_context`, `running_draft`, `running_chat`, etc., the UI sees the session as still running and user input becomes cancel-only. There is no automatic transition to `failed`, `paused`, or a resumable state, so the session can remain wedged indefinitely.

Suggested fix:

Implement explicit startup recovery: mark stale running sessions as `failed` or `paused` with a timeline event, or enqueue a real recovery task. Define a timeout/lease for background operations so the API can distinguish active work from abandoned running state.

### Finding 6: Composer placeholder promises queued input during a run, but submit cancels instead

Severity: High

Evidence:

- `DocAgentComposer` shows the placeholder: "Agent is working — type to queue, or stop to interrupt".
- `ConversationPane.submitOrCancel()` checks `if (isRunning && activeSession)` and immediately calls `api.cancelSession(activeSession.id)`, ignoring the typed input.
- There is no queue endpoint or pending user message state.

Impact:

Users who type a follow-up while the agent is running will cancel the session and lose the typed instruction as an action. This contradicts the UI copy and the product goal of user interrupts and iterative edits.

Suggested fix:

Either implement a real queued/interrupt message path or change the placeholder and send button behavior so typed messages are disabled during running state while the stop button remains explicit. If the desired behavior is interrupt-with-message, send both cancel and a persisted user instruction event, then transition to a resumable state.

### Finding 7: Free-form conversation is artificially unavailable from idle and awaiting-approval states

Severity: High

Evidence:

- `docs/architecture/agent-runtime.md` lists free-form conversation as a required capability.
- `ConversationPane.submitOrCancel()` refuses free-form messages for existing sessions unless status is `draft_ready`, `paused`, or `failed`.
- `session_state.py` only allows `RUNNING_CHAT` from `DRAFT_READY`, `PAUSED`, and `FAILED`.
- `IDLE` allows only `RUNNING_CONTEXT`, `RUNNING_REVISION`, and `CANCELLED`; `AWAIT_OUTLINE_APPROVAL` allows only `RUNNING_DRAFT` and `CANCELLED`.

Impact:

The authoring surface behaves like a constrained workflow: users cannot ask clarifying questions before `/start`, cannot discuss or adjust the outline while awaiting approval, and cannot freely converse at natural decision points. This conflicts with the repository's "document-version Claude Code" north star.

Suggested fix:

Allow `send_message` from `idle` and `await_outline_approval`, with next state preserving or intentionally advancing the current phase. Before coding, decide whether chat from `await_outline_approval` preserves that state after the agent responds or keeps the outline in a revised-awaiting-approval state. Add backend state-machine tests and frontend tests for chat before start and chat during outline review.

### Finding 8: Docker API image does not install OpenHands SDK/runtime dependencies

Severity: Critical

Evidence:

- `agent/runtime-adapters/openhands/docagent_openhands_runtime/client.py` imports `openhands.sdk`, `openhands.tools.preset.default`, and related packages at runtime.
- `pyproject.toml` production dependencies include FastAPI, SQLAlchemy, Celery, Redis, and Postgres drivers, but no OpenHands packages.
- `services/api/Dockerfile` only runs `pip install --no-cache-dir -e .`.
- `scripts/requirements-openhands.txt` is used by `scripts/dev.ps1` to create a host-side OpenHands venv, not by the Docker image.

Impact:

In containerized `DOCAGENT_RUNTIME=openhands` mode, `create_session()` fails with the adapter's "OpenHands SDK packages are required" runtime error even when an OpenHands Agent Server exists. The Docker image cannot execute the documented real-runtime path.

Suggested fix:

Add an optional OpenHands dependency extra and install it in the API/worker image when building an OpenHands-capable image, or split mock and OpenHands images explicitly. Ensure `scripts/requirements-openhands.txt` and Docker dependency declarations do not drift.

### Finding 9: Default Docker/Celery path disables incremental runtime streaming

Severity: High

Evidence:

- `docker-compose.yml` sets `DOCAGENT_QUEUE: celery` for `api`.
- `start_background_runtime_operation()` queues `run_session.delay(...)` whenever `DOCAGENT_QUEUE=celery`.
- `worker_tasks.run_session()` calls `method = getattr(adapter, operation_name)` and then `method(session_id, **operation_kwargs)`.
- Streaming methods such as `send_message_stream()` and `start_loop_stream()` are only used by the inline background runner path in `routes/sessions.py`.
- `docs/superpowers/specs/2026-05-07-runtime-streaming-design.md` promises persisted runtime events as they arrive.

Impact:

The default Docker stack does not stream OpenHands events incrementally. The frontend may open SSE successfully, but timeline updates arrive only after the worker's blocking operation completes. This regresses the observable coding-agent feel the assistant-ui integration is meant to provide.

Suggested fix:

Teach the Celery worker to use streaming adapter methods and persist raw/semantic events through a sink, or set the default dev stack to the inline runner until Celery streaming is implemented. Add a test where `DOCAGENT_QUEUE=celery` uses a fake streaming adapter and proves timeline events appear before the operation completes.

### Finding 10: UI can show stale session running state because operation responses are ignored and session queries are not invalidated on start

Severity: High

Evidence:

- `api.sendMessage`, `api.startLoop`, `api.runChecklist`, and `api.exportMarkdown` return `LoopActionResult` with `status` for background operations.
- `ConversationPane.submitOrCancel()` ignores the returned `status` from `api.sendMessage()` and only calls `refreshTimeline()` and `refreshWorkspace()`.
- Slash command execution in `slashCommands.ts` ignores the returned `status` from `startLoop`, `runChecklist`, and `exportMarkdown`.
- `useSessions()` has `staleTime: 10_000`; session invalidation is driven by SSE events in `useTimeline()`.
- In Docker/Celery mode, streaming events are not emitted until completion.

Impact:

After starting a background operation in the default Docker stack, the UI can continue to believe the session is not running for up to the query stale interval or until completion events arrive. Users may see the wrong composer state, wrong top-bar status, and misleading affordances while work is active.

Suggested fix:

On every accepted background response, invalidate or optimistically update the active session query immediately using the returned `status`. Keep SSE-driven invalidation for subsequent runtime events.

### Finding 11: OpenHands event mapper only recognizes paths in one normalization shape

Severity: Medium

Evidence:

- `packages/timeline/docagent_timeline/openhands_mapper.py` checks for substrings like `"/examples/"` and prefixes like `"versions/"`.
- The same mapper also accepts absolute-looking paths ending in `draft/draft.md` or `context/style_notes.md`.
- `OpenHandsAgentServerClient._extract_path()` recursively extracts arbitrary `path`, `file_path`, or `filename` values from SDK payloads without converting them relative to the workspace.

Impact:

If OpenHands reports absolute paths such as `/workspace/state/workspaces/task-123/versions/v1.md`, `path.startswith("versions/")` will not match, and checkpoint events disappear from the semantic timeline. If Windows-style paths or unexpected absolute container paths are reported, examples and artifact mapping can also become inconsistent.

Suggested fix:

Normalize runtime paths relative to the task workspace inside the OpenHands client or adapter before storing them in raw event payloads. Update mapper tests to cover absolute container paths, Windows paths, and relative workspace paths for every semantic event category.

### Finding 12: Attachment import overwrites files with the same safe stem

Severity: Medium

Evidence:

- `services/api/docagent_api/imports.py` derives `stem = _safe_stem(name)`.
- It writes to fixed paths: `inputs/original/{stem}.txt`, `inputs/markdown/{stem}.md`, and `inputs/reports/{stem}.json`.
- The returned id is also fixed as `input-{stem}`.
- The assistant-ui attachment adapter can import multiple files over the lifetime of one workspace.

Impact:

Uploading `notes.txt` twice, or uploading two different files that normalize to the same stem, silently overwrites the previous input and conversion report. The timeline may contain references to an imported attachment whose content has changed underneath it, breaking auditability and agent context reproducibility.

Suggested fix:

Make imported input paths collision-resistant, for example by appending a short id or timestamp to the safe stem. Preserve the original filename in the conversion report and return stable unique ids.

### Finding 13: Text attachment references are appended as plain prose, not durable structured context

Severity: Medium

Evidence:

- `docAgentAttachmentAdapter.ts` imports the file, then calls `onImported?.("Imported attachment ... as ...")`.
- `useDocAgentAssistantRuntime.ts` appends those reference strings to the user's message text.
- There is no structured message field carrying imported input ids or markdown paths to the backend.

Impact:

The backend and runtime see attachment context only as natural-language text inside a chat message. There is no reliable contract that says which workspace input was attached to which user message, so future reloads, audit views, and agent prompt construction cannot distinguish an attachment reference from ordinary user prose.

Suggested fix:

Extend the send-message API with structured attachment references, or create a timeline/link table from user messages to imported input ids. Keep the prose summary for readability, but make the attachment relationship machine-readable.

### Finding 14: Cancel marks the product session cancelled but does not reliably stop a running background operation

Severity: Critical

Evidence:

- `BackgroundRuntimeRunner` stores `Future` objects but exposes no cancellation method.
- `/sessions/{session_id}/cancel` calls `adapter.cancel(session_id)` in the API process.
- In Docker mode, background operations are executed by Celery in the worker process.
- The OpenHands adapter stores conversations in process-local memory, so the API process may not have the same conversation object that the worker is currently running.
- Celery task execution is not revoked by the cancel endpoint.

Impact:

The UI can show the session as cancelled while the worker continues running and writing files or appending timeline events. In OpenHands mode, cancel may target a different or nonexistent in-process conversation from the one doing work. This can corrupt user expectations, overwrite drafts after cancellation, and leave product state inconsistent with runtime activity.

Suggested fix:

Introduce a cancellable operation lease shared between API and worker. Persist runtime session ids, store active task ids, revoke Celery tasks when cancelling, and have long-running runtime calls poll a cancellation flag or use a runtime-native interrupt. Add an integration test where a slow background operation is cancelled and proves no later draft writes or success state transitions occur.

### Finding 15: Draft autosave can overwrite agent runtime output while an operation is running

Severity: High

Evidence:

- `DraftTab` always calls `useAutoSave(taskId, draft, autoSaveEnabled)` for the active draft tab.
- `AppShell` enables autosave when the draft query belongs to the active task; it does not disable autosave while `activeSession.status` starts with `running`.
- `useAutoSave()` writes the full current Markdown to `PUT /tasks/{task_id}/draft` after 800 ms.
- `services/api/docagent_api/drafts.py` overwrites `draft/draft.md` without version checks, locks, or checkpoint creation.
- Runtime operations also write `draft/draft.md` in the same workspace.

Impact:

If a user has stale draft text in the editor and the agent updates `draft/draft.md`, a delayed autosave can overwrite the agent's output. This is especially risky in the Docker/Celery path where state refresh can lag behind background work. The system can lose runtime-generated content without a checkpoint or conflict indication.

Suggested fix:

Disable editor autosave while any session for the task is running, or add optimistic concurrency to draft updates using file revision/version ids. Manual edits should create checkpoints or conflict records before overwriting an agent-produced draft.

### Finding 16: OpenHands smoke test does not verify the documented Docker/Celery/network path

Severity: High

Evidence:

- `tools/runtime/openhands_smoke.py` uses `TestClient(create_app(repo_root=Path("."), runtime_name="openhands"))`.
- It does not start or call the Docker Compose API service.
- It does not exercise the Nginx `/api` proxy, container DNS, host-to-container OpenHands URL, compose environment injection, or Celery worker handoff.
- The smoke calls endpoints without `background=true`, so it uses the synchronous in-process runtime path.
- `docs/quality/testing.md` presents this as the OpenHands smoke path.

Impact:

The smoke can pass while the actual user path launched by `.\start-dev.cmd -Runtime openhands` is broken. It cannot catch the highest-risk issues in this review: missing compose env, unreachable `127.0.0.1`, missing container OpenHands dependencies, process-local runtime session bindings, or Celery streaming gaps.

Suggested fix:

Add a real full-chain smoke that starts the compose stack with OpenHands selected, calls the web/API through `http://127.0.0.1:5173/api` or `http://127.0.0.1:8000`, uses background operations, and verifies the worker produces timeline and workspace changes. Keep the in-process smoke, but label it as an adapter smoke only.

### Finding 17: CI and E2E coverage exclude the real runtime and Docker path

Severity: Medium

Evidence:

- `.github/workflows/ci.yml` runs Python tests for contracts, workspace, timeline, import tools, API tests, mock adapter tests, and generic tests; it does not run OpenHands adapter tests.
- The web Playwright config forces `$env:DOCAGENT_RUNTIME='mock'` and runs a local Uvicorn process, not Docker Compose.
- `tests/test_dev_entrypoint.py` checks that strings such as `DOCAGENT_RUNTIME` and `OPENHANDS_BASE_URL` appear in `scripts/dev.ps1`, but does not assert they are passed into compose services.

Impact:

The pipeline can stay green while the real OpenHands/Docker path regresses. The current tests validate a mock local development slice, not the assistant-ui-to-runtime-to-Docker chain that the product README advertises.

Suggested fix:

Add at least one non-secret CI-safe Docker Compose smoke for the mock runtime, proving API, worker, web proxy, Postgres, and Redis work together. Add opt-in OpenHands tests behind required secrets, and strengthen `test_dev_entrypoint.py` to parse compose/env behavior instead of string presence.

### Finding 18: SSE reconnection replays the full timeline and relies on client-side id dedupe

Severity: Medium

Evidence:

- `stream_timeline_sse()` initializes `last_row_id = 0` for every new EventSource connection.
- It does not read `Last-Event-ID` or emit SSE `id:` fields.
- The frontend reconnects EventSource after errors and also refetches the full timeline on error.
- Dedupe is based on semantic event `id` in `mergeTimelineEvents()`.

Impact:

Every reconnect replays the entire session timeline from row 1, which can become expensive for long agent sessions. If any event ids are regenerated or duplicated incorrectly, the client can show duplicates or stale ordering. This is not immediately fatal, but it weakens observability under unstable network conditions.

Suggested fix:

Emit SSE `id:` values using the database row id, honor `Last-Event-ID` on reconnect, and keep the client-side full refetch as a recovery fallback rather than the normal replay behavior.

---

## Re-review Pass — 2026-05-12 (Static Analysis)

### Verification of Original Findings

| Finding | Status | Notes |
|---------|--------|-------|
| 1 | **Confirmed** | `docker-compose.yml` has no bare `DOCAGENT_RUNTIME` key; `runtime_factory.py:13` reads it inside the container where it is never injected. |
| 2 | **Confirmed** | `dev.ps1:106` defaults to `http://127.0.0.1:$OpenHandsPort`; `127.0.0.1` resolves to the container itself, not the Windows host. |
| 3 | **Partial** | `worker_tasks.py` now calls `adapter.create_session()` when `get_state()` raises, preventing a crash but creating a **new** OpenHands conversation and losing message history. Structural root cause remains. |
| 4 | **Confirmed** | `client.py:35–37` reads `LLM_API_KEY`/`LLM_MODEL`/`LLM_BASE_URL` from env; none injected by compose. |
| 5 | **Confirmed** | `app.py` only logs; no recovery task in `celery_app.py` or `worker_tasks.py`. |
| 6 | **Confirmed** | `DocAgentComposer` renders a stop button while running, but `useExternalStoreRuntime.onNew` can still call `submitOrCancel()`; `submitOrCancel()` cancels and drops the typed input. The misleading "type to queue" placeholder also remains. |
| 7 | **Partial** | Frontend now shows a hint for disallowed states. `IDLE → RUNNING_CHAT` is still absent from `session_state.py`, so a chat from idle will 409. |
| 8 | **Partial** | Adapter files are copied into the image but `openhands-sdk` is absent from `pyproject.toml`; image fails at `from openhands.sdk import …` at runtime. |
| 9 | **Confirmed** | `docker-compose.yml` sets `DOCAGENT_QUEUE: celery`; worker calls non-streaming `operation_name` methods. |
| 10 | **Partial** | `ConversationPane` calls `refreshTimeline`/`refreshWorkspace` after free-form send, but slash commands and session-list invalidation on session start are still missing. |
| 11 | **Partial** | `openhands_mapper.py` handles both `path` and `file_path`, but it still does not normalize absolute workspace paths to relative paths before checks such as `path.startswith("versions/")`. The original normalization risk remains for several categories. |
| 12 | **Confirmed** | `imports.py` uses a fixed `stem`-based path with no collision avoidance. |
| 13 | **Partial** | Attachment reference is still plain prose appended to message text; no structured link in the payload. |
| 14 | **Confirmed** | `sessions.py` calls `adapter.cancel()` only; no Celery task revocation (`celery_app.revoke()` never called). |
| 15 | **Partial** | `AppShell.tsx:140` gates autosave on `draftTaskId === activeTask?.id` only; running session status is not consulted. |
| 16 | **Confirmed** | `openhands_smoke.py` uses `TestClient` synchronous path; no Docker/Celery involvement. |
| 17 | **Confirmed** | CI excludes `agent/runtime-adapters/openhands/tests`; Playwright forces `DOCAGENT_RUNTIME=mock`; `test_dev_entrypoint.py` only checks string presence. |
| 18 | **Confirmed** | `sessions.py` emits no SSE `id:` field; server always restarts from `last_row_id = 0` on reconnect. |

### Finding 19: `session_status` SSE kind referenced in frontend but never emitted by backend

Severity: Medium

Evidence:

- `apps/web/src/shell/state/useTimeline.ts:83` triggers session cache invalidation on `event.kind === "session_status"`.
- `packages/contracts/docagent_contracts/models.py` — `SemanticEventKind` enum has no `SESSION_STATUS` value.
- `services/api/docagent_api/routes/_shared.py:183–204` — `manual_event()` only emits kinds from `SemanticEventKind`; no code path produces `kind="session_status"`.

Impact:

The cache-invalidation branch for `session_status` is dead code. State changes (e.g., `idle → running_context`) do not propagate to the sessions cache via SSE, so `WorkspacePane` can display stale statuses until the 10-second `staleTime` expires.

Suggested fix:

Emit a `session_status` semantic event (add the kind to the enum and fire it inside `set_session_state()`), or remove the dead `session_status` branch from `useTimeline.ts` and replace it with a general-purpose invalidation trigger on any state-change event.

### Finding 20: `doc_type_id` URL parameter used directly as a path component without sanitization

Severity: High

Evidence:

- `services/api/docagent_api/doctypes.py:17` — `path = root / doc_type_id` with no traversal guard.
- `services/api/docagent_api/prompts.py:16` — `skill_path = repo_root / "doc-types" / doc_type_id / "SKILL.md"` with no sanitization.
- `services/api/docagent_api/workspace_files.py:35–45` — `_resolve_inside()` exists and is used for workspace files but is **not** applied to `doc_type_id` in `doctypes.py` or `prompts.py`.
- `services/api/docagent_api/routes/doctypes.py:21` — `doc_type_id` comes directly from the URL path parameter.

Impact:

A crafted `doc_type_id` can escape the intended `doc-types` root if the router accepts encoded path separators or if the same helper is reused from non-route code. The immediate read target is constrained to a directory containing `SKILL.md`, not arbitrary files, but it still allows unintended directories outside `doc-types` to be treated as document type packs and read into the API response or prompt bundle.

Suggested fix:

Apply the same `_resolve_inside()` guard from `workspace_files.py` to `get_doc_type()` and `build_prompt_bundle()`, or validate that `doc_type_id` contains no path separators or `..` components before constructing the path.

### Finding 21: `list_sessions()` performs an unbounded full-table scan on every call

Severity: Medium

Evidence:

- `services/api/docagent_api/state.py:81–84` — `list_sessions()` issues `SELECT * FROM sessions` with no LIMIT or WHERE clause.
- `services/api/docagent_api/routes/tasks.py:138` — `[s for s in state.list_sessions() if s["task_id"] == task_id]` loads all sessions then filters in Python.
- `services/api/docagent_api/app.py:78` — `state.list_sessions()` called unconditionally on every `create_app()` / hot-reload.

Impact:

As sessions accumulate, `GET /tasks/{id}/sessions` and the startup interrupted-session scan become progressively slower. The startup scan runs inside `create_app()`, which fires on every uvicorn `--reload` cycle.

Suggested fix:

Add a `task_id` parameter to `list_sessions()` and push the filter into SQL. Add a `status IN (...)` clause to the interrupted-session query in `app.py`.

### Finding 22: Concurrent Celery dispatch can enqueue two operations for the same session

Severity: High

Evidence:

- `services/api/docagent_api/celery_app.py` — no per-session concurrency limit; Celery defaults to `cpu_count()` concurrent workers.
- `services/api/docagent_api/routes/_shared.py:129–132` — `runner.is_running()` guard only tracks inline `BackgroundRuntimeRunner` work. It does not know about Celery tasks already accepted by another API process.
- `services/api/docagent_api/routes/_shared.py:136–148` — the Celery dispatch path has no distributed lock or active-task table.
- `prepare_transition()` writes the running state before enqueueing, so two sequential requests in one process are likely rejected; the remaining risk is concurrent requests/API replicas that read the same prior state before either save is committed.

Impact:

Two near-simultaneous requests (e.g., double-submit `/loop/start`) can enqueue two Celery tasks for the same session, causing concurrent OpenHands operations, duplicate timeline events, and undefined draft state.

Suggested fix:

Add a Redis-backed distributed lock (e.g., via `celery-once` or a manual `SET NX EX` lock) keyed on `session_id` before dispatching a new Celery task, or add a `UNIQUE` constraint on `(session_id, status)` for running states to let the DB enforce exclusivity.

### Finding 23: `create_app()` ignores `DOCAGENT_REPO_ROOT` environment variable — relies on `Path.cwd()` fallback

Severity: Medium

Evidence:

- `services/api/docagent_api/app.py:47` — `root = repo_root or Path.cwd()` when no argument is passed via the factory.
- `docker-compose.override.yml:6` — `DOCAGENT_REPO_ROOT: /app` is set in the `api` service env, but `create_app()` never reads it.
- `services/api/docagent_api/worker_tasks.py:33` — the Celery worker correctly reads `os.environ.get("DOCAGENT_REPO_ROOT", ".")`.

Impact:

The API currently works by accident because `Path.cwd()` == `/app` == `DOCAGENT_REPO_ROOT`. Any change to the Docker `WORKDIR` or running the API outside Docker without an explicit argument silently uses the wrong repository root for skill lookups and doc-type resolution.

Suggested fix:

Change `create_app()` to read `root = repo_root or Path(os.environ.get("DOCAGENT_REPO_ROOT", "."))`, matching the worker's behavior.

### Finding 24: Additional evidence for Finding 15 — draft autosave is not gated on running session status

Severity: Duplicate of Finding 15

Evidence:

- `apps/web/src/shell/editor/useAutoSave.ts:16–33` — fires `api.updateDraft()` 800 ms after any `markdown` change when `enabled=true`.
- `apps/web/src/shell/AppShell.tsx:140` — `draftAutoSaveEnabled` is gated only on `draftTaskId === activeTask?.id`; `isRunning` is not consulted.
- `services/api/docagent_api/routes/tasks.py:99–102` — `PUT /tasks/{id}/draft` calls `write_draft()` with no running-session guard on the backend.

Impact:

This is a more specific restatement of Finding 15 with additional frontend and backend evidence. It should be merged into Finding 15 when converting the review into implementation tasks rather than counted as a separate defect.

Suggested fix:

Pass `isRunning` (derived from `activeSession?.status`) into the `draftAutoSaveEnabled` condition in `AppShell.tsx`. Optionally add a session-state guard to `PUT /tasks/{id}/draft` that returns 409 while a running session exists for the task.

### Finding 25: Slash commands do not call `refreshTimeline` after dispatching — UI stays stale until SSE delivers

Severity: Low

Evidence:

- `apps/web/src/shell/conversation/slashCommands.ts:39–52` — `/start`, `/check`, `/export` call the API and set `handled = true` without calling `context.refreshTimeline()`.
- `apps/web/src/shell/panes/ConversationPane.tsx:67–78` — after `executeSlashCommand` returns `handled=true`, no refresh is triggered.
- Compare with `ConversationPane.tsx:91–93` — the free-form message path calls both `refreshTimeline` and `refreshWorkspace`.

Impact:

After typing `/start`, the conversation thread shows no new events until SSE delivers them (≥200 ms). The session status badge remains `idle` until the next `staleTime` expiry (10 s). This is a UX inconsistency relative to the free-form message path.

Suggested fix:

Call `context.refreshTimeline()` inside each handled slash command branch in `slashCommands.ts`, or call it unconditionally in `ConversationPane.submitOrCancel()` after `executeSlashCommand` returns `handled=true`.

---

## Post-Merge Re-review — 2026-05-12

Context: after commit `07ee848` merged runtime/dev-container and assistant-ui fixes, the repository was rechecked against this review. `git status --short --branch` showed `main...origin/main` with a clean worktree. `docker compose config` was also run with `DOCAGENT_RUNTIME=openhands`, `OPENHANDS_CONTAINER_BASE_URL=http://host.docker.internal:8001`, and dummy LLM env values.

### Current Status Summary

| Finding | Current Status | Notes |
|---------|----------------|-------|
| 1 | **Resolved for default dev compose path; still needs base/CI coverage** | `docker-compose.override.yml` now injects `DOCAGENT_RUNTIME` into both `api` and `worker`, and `docker compose config` confirms the merged config contains it. Base `docker-compose.yml` still lacks the key, so non-dev compose/CI coverage should still be verified. |
| 2 | **Resolved for Docker Desktop dev path** | `scripts/dev.ps1` now derives `OPENHANDS_CONTAINER_BASE_URL=http://host.docker.internal:$OpenHandsPort`, and merged compose config passes that value as `OPENHANDS_BASE_URL` to `api` and `worker`. |
| 3 | **Still open** | `OpenHandsRuntimeAdapter` still stores `_runtime_session_ids` in memory, and `worker_tasks._ensure_runtime_session()` still creates a new runtime session when process-local state is absent. |
| 4 | **Resolved for default dev compose path; still needs base/CI coverage** | `docker-compose.override.yml` now injects `OPENHANDS_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, and `LLM_BASE_URL` into both `api` and `worker`; merged compose config confirms the values. |
| 5 | **Still open** | `create_app()` still only logs interrupted running sessions; no recovery task exists in `worker_tasks.py` or `celery_app.py`. |
| 6 | **Still open** | `DocAgentComposer` still uses `submitMode="enter"` and the running placeholder still says "type to queue"; `ConversationPane.submitOrCancel()` still cancels on non-empty input while running. |
| 7 | **Still open** | Frontend hints exist, but `session_state.py` still does not allow `IDLE -> RUNNING_CHAT` or `AWAIT_OUTLINE_APPROVAL -> RUNNING_CHAT`. |
| 8 | **Resolved for current Dockerfile** | `pyproject.toml` now defines an `openhands` extra and `services/api/Dockerfile` installs `pip install --no-cache-dir -e ".[openhands]"`. |
| 9 | **Still open; new evidence** | Route handlers build streaming callables, but the Celery branch passes `operation_name="start_loop"`/`"approve_outline"`/etc. to `worker_tasks.run_session()`. The worker calls those sync methods directly, so Docker/Celery still does not stream incrementally. |
| 10 | **Still partial** | Free-form send refreshes timeline/workspace, but handled slash commands still return before calling `refreshTimeline()` or session invalidation. |
| 11 | **Still open** | `openhands_mapper.py` still only replaces backslashes; absolute workspace/container paths are not normalized relative to workspace root. |
| 12 | **Still open** | `imports.py` still writes fixed stem-based paths and ids. |
| 13 | **Still partial/open** | Attachment adapter still returns prose content such as "Imported attachment ..."; no structured attachment reference reaches `SendMessageRequest`. |
| 14 | **Still open** | Cancel still calls the API-process adapter only; no Celery revoke or shared cancellation flag is present. |
| 15 | **Still open** | `AppShell.tsx` still gates autosave only on `draftTaskId === activeTask?.id`; running session status is not consulted. Backend draft PUT has no running guard. |
| 16 | **Still partial/open** | Dev entrypoint tests are stronger, but no compose/OpenHands/Celery full-chain smoke exists. |
| 17 | **Still partial/open** | Tests now assert more dev-entrypoint details, but CI still lacks a real Docker/Celery/OpenHands full-chain job. |
| 18 | **Still open** | SSE still starts with `last_row_id = 0`, emits only `data: ...`, and does not honor `Last-Event-ID`. |
| 19 | **Still open** | Frontend still listens for `session_status`; backend still does not emit that semantic event kind. |
| 20 | **Still open** | `get_doc_type()` and `build_prompt_bundle()` still join raw `doc_type_id` into filesystem paths. |
| 21 | **Still open** | `state.list_sessions()` still returns every session, and route handlers filter in Python. |
| 22 | **Still open** | Celery dispatch still lacks a distributed per-session lock or active operation lease. |
| 23 | **Still open** | `create_app()` still uses `repo_root or Path.cwd()` and ignores `DOCAGENT_REPO_ROOT`. |
| 24 | **Still duplicate/open** | Same root cause as Finding 15 remains. |
| 25 | **Still open** | `slashCommands.ts` still calls `/start`, `/check`, and `/export` without refresh/invalidation. |

### New Evidence To Fold Into Fix Plan

- Finding 9 should explicitly cover the current half-wired streaming path: `sessions.py` constructs streaming callables for inline execution, but the Celery path passes only the sync operation name to `worker_tasks.run_session()`. The worker never receives the stream method name or a runtime event sink.
- Phase 1 of the fix plan should be reduced to verification and remaining hardening for the dev Docker path. The runtime/env/OpenHands dependency parts are already implemented for the default dev compose path; the remaining Phase 1 work is security validation, `DOCAGENT_REPO_ROOT` handling, diagnostics, and CI/base-compose coverage decisions.

---

## Post-Merge Static Analysis Pass — 2026-05-12

### Finding 26: nginx `rewrite` regex accepts `/api/` bare path — routing contract is ambiguous

Severity: Low

Evidence:

- `apps/web/nginx.conf:12–13` — `rewrite ^/api/(.*)$ /$1 break` captures an empty string for `/api/`, rewriting it to `/` before proxying to FastAPI.
- FastAPI currently has no explicit `/` route, so this normally returns 404 rather than application data. The behavior is not a security issue, but the proxy contract is implicit.

Impact:

A bare `/api/` browser request is routed through the API proxy even though it is not a real API endpoint. This is a minor routing clarity issue and should not block the runtime-chain fixes.

Suggested fix:

If the project wants strict proxy semantics, change the regex to `^/api/(.+)$` (require at least one character after the prefix), or add an explicit `location = /api/ { return 404; }` block. Otherwise document the current behavior and leave it alone.

### Finding 27: `docker-compose.override.yml` hardcodes `DOCAGENT_REPO_ROOT: /app` — cannot be overridden via host environment

Severity: Low

Evidence:

- `docker-compose.override.yml:6,22` — `DOCAGENT_REPO_ROOT: /app` is a literal string in both `api` and `worker` blocks.
- All other runtime env vars use `${VAR:-default}` interpolation syntax.
- If the container workdir changes (e.g., alternative deployment), there is no host-env override path.

Impact:

No correctness bug under current Docker setup. Minor ops inflexibility for alternative deployment layouts.

Suggested fix:

Change to `DOCAGENT_REPO_ROOT: ${DOCAGENT_REPO_ROOT:-/app}` to match the interpolation pattern used by other vars.

### Finding 28: Celery `run_session()` rollback depends on callers passing `previous_state_on_failure`

Severity: Medium

Evidence:

- `worker_tasks.py:24–45` — `_ensure_runtime_session()` raises on failure; no inner try/except.
- `worker_tasks.py:70–86` — the outer `except` block sets rollback to `previous_state_on_failure or session["status"]`.
- Normal route dispatch currently passes the pre-running state into Celery, so common API paths roll back to the state before the operation. However, direct task invocation, future callers, or malformed dispatches can omit `previous_state_on_failure` while the DB session is already `running_*`.

Impact:

The task contract is fragile: the worker appends a failed timeline event, but its rollback target is only safe if every caller passes the pre-running state. A future caller can leave the session in `running_*` after a worker-side `_ensure_runtime_session()` failure.

Suggested fix:

Make the Celery contract explicit and defensive. Require `previous_state_on_failure` for route-dispatched operations, add tests for the normal route path, and add a fallback that maps missing rollback state plus current `running_*` status to `FAILED` instead of preserving `running_*`.

### Finding 29: `OpenHandsAgentServerClient._conversations` is process-local — root cause of Finding 3

Severity: Critical

Evidence:

- `agent/runtime-adapters/openhands/docagent_openhands_runtime/client.py:30` — `self._conversations: dict[str, Any] = {}` is an instance variable.
- `services/api/docagent_api/runtime_factory.py:22` — `create_runtime_adapter()` constructs a fresh `OpenHandsAgentServerClient` (and thus a fresh `_conversations` dict) on every call.
- `services/api/docagent_api/worker_tasks.py:21` — `_get_adapter()` calls `create_runtime_adapter()` on every Celery task invocation.
- Every Celery worker invocation therefore starts with `_conversations = {}`, so `_ensure_runtime_session` always falls through to `adapter.create_session()`, creating a new OpenHands conversation.

Impact:

This is the structural root cause of Finding 3. Even after Finding 3's symptom (crash on get_state miss) was patched, the underlying issue remains: every worker task silently forks a new OpenHands conversation. Message history, context, and conversation continuity are permanently broken across API ↔ worker process boundaries in the current architecture.

Suggested fix:

The fix requires either (A) persisting the OpenHands `conversation_id` in the product DB (as `sessions.runtime_session_id`) and loading it in the worker via the OpenHands server's REST API instead of the in-process dict, or (B) making `_get_adapter()` return a process-scoped singleton adapter instance (module-level). Option A is the correct long-term fix (aligns with Phase 2 plan); Option B is a shorter-term workaround but breaks the stateless-worker design.

### Finding 30: OpenHands image lacks import-time smoke for pinned `lmnr==0.7.51` on Python 3.12

Severity: Low

Evidence:

- `pyproject.toml:23` — `"lmnr==0.7.51"` in the `[openhands]` dependency group.
- `services/api/Dockerfile:1` — `FROM python:3.12-slim` (bumped from 3.11 in this merge).
- The local checkout does not currently have `lmnr` installed (`python -c "import importlib.util; print(importlib.util.find_spec('lmnr'))"` returned `None`), so import compatibility cannot be proven from the host environment.

Impact:

The Docker build can complete dependency installation while still missing a cheap import-time compatibility signal for a pinned OpenHands dependency on Python 3.12. This is a smoke-test gap, not a confirmed dependency bug.

Suggested fix:

Add `python -c "import lmnr"` to a Dockerfile smoke step or CI job that runs inside the OpenHands-capable image. Upgrade or repin only if that smoke fails.

### Finding 32: Mock-runtime compose still receives an OpenHands base URL by default

Severity: Low

Evidence:

- `docker-compose.override.yml:8,24` — `OPENHANDS_BASE_URL` defaults to `${OPENHANDS_CONTAINER_BASE_URL:-http://host.docker.internal:8001}` for both `api` and `worker`.
- Therefore mock-runtime containers still receive an OpenHands-looking URL even when `DOCAGENT_RUNTIME=mock`.
- If a developer runs `scripts/dev.ps1` directly in a long-lived PowerShell process, `$env:OPENHANDS_CONTAINER_BASE_URL` can also remain set between invocations. This does not affect the parent shell when using `start-dev.cmd`, but it can add confusion for direct script use.

Impact:

No functional breakage for the mock adapter. The environment is misleading during runtime switches and can make compose output look like OpenHands is configured even when the selected runtime is mock.

Suggested fix:

Make the runtime-specific env contract explicit: either leave `OPENHANDS_BASE_URL` blank when `DOCAGENT_RUNTIME=mock`, or document that it is harmless. If keeping direct `scripts/dev.ps1` use supported, clear `OPENHANDS_CONTAINER_BASE_URL` when runtime is not `openhands`.

### Finding 33: Project Python version range conflicts with OpenHands extra

Severity: Medium

Evidence:

- `pyproject.toml` declared `requires-python = ">=3.11"`.
- The OpenHands packages pinned in `[project.optional-dependencies].openhands` require Python 3.12 or newer.
- Running `uv run python -m pytest ...` attempted to resolve the project including supported Python 3.11 and failed because `openhands-agent-server==1.20.1` cannot satisfy Python 3.11.
- `services/api/Dockerfile` already uses `FROM python:3.12-slim`, and `services/api/README.md` says the API and worker image uses Python 3.12 because the OpenHands SDK packages require it.

Impact:

Local and CI dependency resolution can fail even before tests run, depending on the resolver and whether optional dependency metadata is considered. This undermines the OpenHands-capable image/development path even though the runtime image itself is Python 3.12.

Suggested fix:

Align the project metadata with the runtime contract by setting `requires-python = ">=3.12"` and updating startup guidance that still mentions Python 3.11.
