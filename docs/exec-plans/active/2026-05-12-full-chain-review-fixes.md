# Full Chain Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the assistant-ui to backend to agent runtime to Docker execution chain so the documented OpenHands and Docker paths are real, observable, cancellable, and covered by tests.

**Architecture:** Treat this as a full-chain reliability pass, not a UI-only or Docker-only patch. Stabilize configuration and runtime identity first, then state/cancellation/streaming, then frontend refresh and editing safety, then security/performance cleanup and verification.

**Tech Stack:** React 19, assistant-ui, TanStack Query, FastAPI, SQLAlchemy/Postgres, Celery/Redis, Docker Compose, OpenHands SDK/Agent Server, pytest, Vitest, Playwright.

---

## Goal

Resolve the findings in `docs/reviews/active/2026-05-12-assistant-ui-runtime-docker-chain-review.md` with staged, testable changes that keep the product aligned with a document-version Claude Code experience.

## Scope

- Docker Compose runtime environment propagation and OpenHands host/container networking.
- Runtime session identity persistence across API and worker processes.
- Background operation lifecycle: streaming, cancellation, recovery, concurrency.
- Frontend assistant-ui behavior: running-state handling, slash-command refresh, session cache updates, draft autosave safety.
- Workspace/import safety: doc type path validation and unique input import paths.
- Timeline/SSE correctness and session status invalidation.
- CI, smoke, and docs coverage for the real chain.

## Non-Goals

- Do not redesign the entire runtime adapter interface beyond what is needed for persisted runtime identity and cancellation.
- Do not build a full enterprise deployment topology.
- Do not replace Celery with another queue.
- Do not implement binary import/conversion in this pass.
- Do not turn the authoring loop into a fixed workflow engine.

## Finding Coverage Map

| Workstream | Findings |
|---|---|
| Runtime/Docker configuration | 1✓, 2✓, 4✓, 8✓ (resolved by 07ee848); verify/CI coverage remains for 16, 17; harden 20 (security), 23, 27, 32 |
| Runtime identity and worker lifecycle | 3, 5, 9, 14, 22, 28, 29 |
| Frontend interaction and refresh | 6, 7, 10, 19, 25 |
| Draft/editing and attachment safety | 12, 13, 15, 24 |
| Path/SSE/performance hardening | 11, 18, 21, 26 |
| Low-severity ops / compat | 30, 33 |

## Current Baseline After 2026-05-12 Merge

Commit `07ee848` partially repaired the runtime/Docker entry path:

- `docker-compose.override.yml` now injects `DOCAGENT_RUNTIME`, `OPENHANDS_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, and `LLM_BASE_URL` into both `api` and `worker`.
- `scripts/dev.ps1` now sets a container-safe `OPENHANDS_CONTAINER_BASE_URL` default of `http://host.docker.internal:$OpenHandsPort`.
- `pyproject.toml` now defines OpenHands dependencies and `services/api/Dockerfile` installs `.[openhands]`.
- `apps/web/nginx.conf` now resolves the API upstream dynamically through Docker DNS.

The same merge did not close the runtime lifecycle issues. The highest-risk remaining chain breaks are persisted runtime session identity, stale running recovery, Celery streaming, cancellation, session status/SSE semantics, autosave conflict prevention, doc type path validation, and query/attachment hardening.

## Files And Modules Likely To Change

- `docker-compose.yml`: decide whether runtime, LLM, and OpenHands env should also be present in the base compose file, or whether base compose remains mock-safe and runtime env lives in the dev override.
- `docker-compose.override.yml`: current dev-path runtime/OpenHands env injection, container-safe host URL, and repo-root override.
- `scripts/dev.ps1`: translate host OpenHands URL for containers; pass env into compose reliably.
- `.env.example`: document runtime envs and container-safe OpenHands URL.
- `pyproject.toml`: add OpenHands optional dependency extra or runtime dependency grouping; keep `requires-python` compatible with OpenHands packages.
- `services/api/Dockerfile`: install optional OpenHands dependencies when requested.
- `services/api/docagent_api/db.py`: add runtime session binding and active operation tables/columns if needed.
- `services/api/alembic/versions/*`: add migration for runtime binding/operation lease if schema changes are used.
- `services/api/docagent_api/state.py`: query sessions by task/status; persist runtime binding and active operation metadata.
- `services/api/docagent_api/app.py`: read `DOCAGENT_REPO_ROOT`; use filtered interrupted-session query.
- `services/api/docagent_api/runtime_factory.py`: expose selected runtime diagnostics if needed.
- `services/api/docagent_api/routes/_shared.py`: emit status events, use distributed operation lock, stream in worker path, and centralize state transitions.
- `services/api/docagent_api/routes/sessions.py`: start/cancel/background behavior, SSE ids, Last-Event-ID support.
- `services/api/docagent_api/routes/tasks.py`: structured attachments, safe draft update guard, filtered session queries.
- `services/api/docagent_api/doctypes.py`: validate doc type ids and contain paths under `doc-types`.
- `services/api/docagent_api/prompts.py`: validate doc type path before reading `SKILL.md`.
- `services/api/docagent_api/imports.py`: collision-resistant import ids and paths.
- `services/api/docagent_api/worker_tasks.py`: use persisted runtime binding, stream events, honor cancellation/locks.
- `agent/runtime-adapters/openhands/docagent_openhands_runtime/adapter.py`: accept persisted runtime session binding; normalize paths; expose cancel behavior.
- `agent/runtime-adapters/openhands/docagent_openhands_runtime/client.py`: normalize event paths relative to workspace.
- `packages/contracts/docagent_contracts/runtime.py`: runtime binding/cancellation/streaming contract updates if needed.
- `packages/contracts/docagent_contracts/models.py`: add `SESSION_STATUS` semantic event kind if using timeline invalidation.
- `packages/timeline/docagent_timeline/openhands_mapper.py`: normalize paths and cover absolute/Windows/container paths.
- `apps/web/src/api.ts`: structured attachments and possibly session response handling.
- `apps/web/src/shell/panes/ConversationPane.tsx`: running input behavior, optimistic session invalidation, slash command refresh.
- `apps/web/src/shell/conversation/slashCommands.ts`: refresh/invalidate after handled commands.
- `apps/web/src/shell/state/useTimeline.ts`: session status invalidation and SSE Last-Event-ID behavior.
- `apps/web/src/shell/AppShell.tsx`: disable autosave during running sessions.
- `apps/web/src/shell/assistant/docAgentAttachmentAdapter.ts`: structured attachment references.
- `tools/runtime/openhands_smoke.py`: relabel as adapter smoke or add full-chain mode.
- `tools/runtime/compose_smoke.py`: new compose/API smoke script.
- `.github/workflows/ci.yml`: include OpenHands adapter unit tests and mock Docker smoke if feasible.
- `README.md`, `services/api/README.md`, `docs/quality/local-development.md`, `docs/quality/testing.md`: update real runtime setup and verification.

## Step-By-Step Implementation Checklist

### Phase 1: Verify And Harden Runtime Configuration In Docker

- [x] **[Security — Finding 20, do first]** Validate `doc_type_id` in `get_doc_type()` (`doctypes.py`) and `build_prompt_bundle()` (`prompts.py`): reject any value containing `..`, `/`, `\`, or URL-encoded equivalents before constructing the path. Add tests for traversal attempts via `/doc-types/{id}` and `POST /tasks`.
- [x] Replace the old compose-string tests with a merged-config assertion: run or parse `docker compose config` with `DOCAGENT_RUNTIME=openhands` and dummy LLM env, and assert `api` and `worker` receive `DOCAGENT_RUNTIME`, container-safe `OPENHANDS_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, and `LLM_BASE_URL`.
- [x] Decide whether base `docker-compose.yml` should also include runtime/OpenHands env keys, or whether the supported contract is "dev/runtime env lives in `docker-compose.override.yml`". Document the decision in `docs/quality/local-development.md` and tests.
- [x] Verify `scripts/dev.ps1` continues translating host-side `http://127.0.0.1:8001` to container-side `http://host.docker.internal:8001`; keep this covered by `tests/test_dev_entrypoint.py`.
- [x] **[Finding 32]** Decide and document the mock-runtime OpenHands env contract: either leave `OPENHANDS_BASE_URL` blank when `DOCAGENT_RUNTIME=mock`, or explicitly document why the compose default is harmless. If direct `scripts/dev.ps1` use remains supported, clear `OPENHANDS_CONTAINER_BASE_URL` when runtime is not `openhands`.
- [x] Update `.env.example` with comments distinguishing host `OPENHANDS_BASE_URL` from container `OPENHANDS_CONTAINER_BASE_URL`, if the file does not already reflect the merged behavior.
- [x] **[Finding 23]** Update `create_app()` to read `DOCAGENT_REPO_ROOT` when `repo_root` is not explicitly passed: `root = repo_root or Path(os.environ.get("DOCAGENT_REPO_ROOT", "."))`.
- [x] **[Finding 27]** Change `DOCAGENT_REPO_ROOT: /app` in `docker-compose.override.yml` (both `api` and `worker`) to `DOCAGENT_REPO_ROOT: ${DOCAGENT_REPO_ROOT:-/app}` for consistency with other interpolated vars.
- [x] Keep the current OpenHands dependency strategy (`pyproject.toml` `[project.optional-dependencies].openhands` plus Dockerfile `.[openhands]`) unless image size or CI runtime proves it needs split image targets.
- [x] **[Finding 33]** Align `pyproject.toml` `requires-python` with the OpenHands dependency floor and Docker runtime by requiring Python 3.12+.
- [x] **[Finding 30]** Add an import-time smoke for the OpenHands-capable image: run `python -c "import lmnr"` inside Docker build or CI. Treat this as a smoke gap; only repin/upgrade `lmnr==0.7.51` if the smoke fails on Python 3.12.
- [x] Add an API health/runtime diagnostics test that confirms selected runtime is visible without exposing secrets.
- [ ] Verification: run `python -m pytest tests/test_dev_entrypoint.py services/api/tests/test_runtime_factory.py -q`.
- [ ] Verification: run `docker compose config` and inspect that `api` and `worker` contain the runtime env keys.

### Phase 2: Persist Runtime Session Identity And Operation Leases

- [ ] Add a schema migration for: `sessions.runtime_session_id TEXT`, `sessions.celery_task_id TEXT` (for cancel/revoke), and `sessions.runtime TEXT`. Each column is nullable and additive-only. Include a `downgrade` stub.
- [ ] Decide and document operation lease strategy before implementing: **Redis `SET NX EX`** (ephemeral, TTL must exceed longest expected operation — recommend 30 min) vs **DB column `sessions.celery_task_id` uniqueness check** (durable across restarts, cleared on startup recovery). DB-based is simpler to reason about for this stack.
- [ ] Before implementing resume, verify the current OpenHands Agent Server/SDK supports reconnecting to an existing conversation by id across API/worker processes. Record the exact supported API in the implementation PR. If unsupported, choose and document one explicit fallback: fail and clear stale state, create a new product session, or pin OpenHands execution to the creating worker. Do not silently create a second runtime conversation for the same product session.
- [ ] Extend `DocAgentState` with methods to save/load runtime binding, list sessions by task id, list sessions by status, acquire/release an operation lease, and mark stale operations.
- [ ] Update `OpenHandsRuntimeAdapter` so `create_session()` returns or records the runtime session id through a product-level binding, and follow-up operations can use a persisted binding instead of only `_runtime_session_ids`.
- [ ] Update `worker_tasks._ensure_runtime_session()` so it loads existing runtime binding rather than creating a second OpenHands conversation when process-local state is empty.
- [ ] Add tests where session creation happens with one adapter instance and background operation runs with another instance, proving the same runtime session id is used.
- [ ] Add Redis or DB-backed per-session operation lease before Celery dispatch; reject concurrent operations with HTTP 409.
- [ ] Add stale running-session recovery on API startup or worker startup: append an error/status event and move abandoned sessions to `failed` or `paused`.
- [ ] **[Finding 28]** Make Celery rollback contract explicit and defensive: require route-dispatched tasks to pass `previous_state_on_failure`, add tests that normal route dispatch rolls back to the pre-running state, and add a fallback where missing rollback state plus current `running_*` status becomes `FAILED` instead of preserving `running_*`.
- [ ] **[Finding 29 — root cause of Finding 3]** Confirm whether the current OpenHands Agent Server/SDK exposes a REST endpoint to reconnect to an existing conversation by `conversation_id`. If yes, implement persistence path: `client.py` resumes via server API using `sessions.runtime_session_id` from DB. If no, choose and document one explicit fallback strategy (see Open Questions) and implement it — do not silently create a second conversation.
- [ ] Add cancellation plumbing: persist Celery task id or operation id, revoke Celery tasks where possible, and make worker/runtime calls check a cancellation flag before final writes/state transitions.
- [ ] Verification: run `python -m pytest services/api/tests/test_worker_tasks.py services/api/tests/test_background_runner.py services/api/tests/test_phase3_api.py agent/runtime-adapters/openhands/tests -q`.

### Phase 3: Restore Streaming And Timeline State Semantics

- [ ] Add a regression test for the current half-wired Celery streaming path: with `DOCAGENT_QUEUE=celery` and a fake adapter that implements `start_loop_stream`, assert the queued task receives/uses the streaming method rather than `start_loop`.
- [ ] **Streaming dispatch — decide and implement one approach:** (A) Route layer passes `operation_name="start_loop_stream"` when `use_celery=True` and streaming method exists; worker calls it directly with a local `runtime_event_sink()`. (B) Worker auto-detects `f"{operation_name}_stream"` and calls it if present. Approach A is simpler since `stream_or_sync()` logic already exists in the route layer.
- [ ] Update `worker_tasks.run_session()` so streaming methods receive a `runtime_event_sink(state, task_id, session_id)` and persist raw/semantic events before operation completion. Keep sync fallback behavior for adapters without stream methods.
- [ ] Add a fake streaming adapter test with `DOCAGENT_QUEUE=celery` proving a timeline event is persisted before the operation completes.
- [ ] Add `SESSION_STATUS` to `SemanticEventKind` or introduce a documented status event mechanism.
- [ ] **`set_session_state()` signature change required:** to emit a `SESSION_STATUS` timeline event, add optional `task_id: str | None = None` parameter. When `task_id` is present, emit the status event. Update all ~10 call sites (routes/sessions.py, routes/tasks.py, worker_tasks.py) to pass `task_id` where available. List all call sites in the PR description.
- [ ] Emit a session status event whenever `set_session_state()` is called with a non-None `task_id`.
- [ ] Update `useTimeline.ts` to invalidate sessions on real status events and errors.
- [ ] Add SSE `id:` fields based on timeline row id and honor `Last-Event-ID` in `/timeline/stream`.
- [ ] Keep full timeline fetch on frontend SSE error as a recovery path, but avoid normal full replay on reconnect.
- [ ] Normalize OpenHands paths relative to `workspace_root` before mapping; support absolute container paths, Windows paths, and relative paths.
- [ ] Verification: run `python -m pytest services/api/tests/test_sse.py packages/timeline/tests/test_openhands_mapper.py -q`.
- [ ] Verification: run `cd apps/web; npm run test:unit -- useTimeline`.

### Phase 4: Fix Assistant UI Interaction And Editing Safety

> **Coding gate:** Resolve the following Open Questions before coding begins, as they determine the backend state transitions and frontend affordances. Record the decision in this plan or in the implementation PR before changing state-machine or composer behavior:
> - Does chat from `await_outline_approval` preserve that state after the agent responds, or advance it?
> - Are manual draft edits during a running operation blocked entirely, or allowed as explicit interrupt checkpoints?

- [ ] Decide and document running-input behavior: either disable send while running or implement interrupt-with-message. For this pass, prefer disabling message send while running and keeping an explicit stop button.
- [ ] Fix Enter-key cancel bug (two-part, must be done together): (1) Set `submitMode="none"` on `ComposerPrimitive.Input` when `isRunning=true` so Enter does not trigger submission. (2) In `submitOrCancel()`, change the `isRunning && activeSession` branch to only call `cancelSession()` when `input.trim() === ""` — non-empty input while running should show a hint or be no-op, not silently cancel.
- [ ] Update `DocAgentComposer` placeholder text to remove the "type to queue" promise — replace with "Agent is working" or similar non-committal copy unless real queueing is implemented.
- [ ] Allow free-form `send_message` from `idle` and `await_outline_approval`, or explicitly document why those states are blocked. Preferred fix: allow chat from both while preserving or returning to the prior phase state.
- [ ] Update `session_state.py` tests for `IDLE -> RUNNING_CHAT` and `AWAIT_OUTLINE_APPROVAL -> RUNNING_CHAT`.
- [ ] After any accepted background response, optimistically update or invalidate the active session query using returned `status`.
- [ ] Update slash commands to call `refreshTimeline()` and session invalidation after dispatch.
- [ ] Disable draft autosave while any active session for the task has a `running_*` status.
- [ ] Add backend guard on `PUT /tasks/{task_id}/draft` so draft writes during running sessions return 409 unless explicitly forced.
- [ ] Verification: run `cd apps/web; npm run test:unit`.
- [ ] Verification: run `python -m pytest services/api/tests/test_session_state.py services/api/tests/test_phase3_api.py services/api/tests/test_doctypes_and_drafts.py -q`.

### Phase 5: Harden Inputs, Paths, And Query Shape

> Note: doc type id path traversal (Finding 20) was addressed in Phase 1. Steps 1–3 below are verification-only; do not re-implement.

- [ ] Verify Phase 1 security coverage: confirm `get_doc_type()` and `build_prompt_bundle()` reject traversal attempts and that tests pass for `/doc-types/{id}` and session creation with malicious `doc_type_id`.
- [ ] **[Finding 26]** Decide whether to enforce strict nginx `/api/` proxy semantics. If yes, change regex to `^/api/(.+)$` or add `location = /api/ { return 404; }`. If no, document that bare `/api/` is harmless and currently returns the backend's root behavior.
- [ ] Make `import_text_input()` produce unique ids and paths for duplicate filenames, preserving the original filename in the conversion report.
- [ ] **[API contract change — requires migration plan]** Extend `SendMessageRequest` and response to carry structured attachment references (`attachments: [{input_id, markdown_path, original_filename}]`). Make the field optional for backward compatibility. Update `apps/web/src/api.ts`, `docAgentAttachmentAdapter.ts`, and all `sendMessage` call sites. Keep the human-readable imported attachment line in the message summary.
- [ ] Replace unbounded `list_sessions()` usage in task session listing with a DB-level `task_id` filter.
- [ ] Replace startup interrupted-session scan with a DB-level status filter.
- [ ] Verification: run `python -m pytest services/api/tests/test_imports.py services/api/tests/test_doctypes_and_drafts.py services/api/tests/test_state.py services/api/tests/test_phase2_api.py -q`.
- [ ] Verification: run `cd apps/web; npm run test:unit -- docAgentAttachmentAdapter`.

### Phase 6: Add Real Chain Verification And Documentation

- [ ] Rename or document `tools/runtime/openhands_smoke.py` as an adapter smoke, not a full-chain smoke.
- [ ] Add a mock Docker Compose smoke script that starts `postgres redis api worker web`, creates a workspace through the published API/proxy, starts a background operation, and verifies timeline/workspace output.
- [ ] Add an opt-in OpenHands full-chain smoke that uses compose, background operations, and the container-safe OpenHands URL.
- [ ] Add OpenHands adapter tests to CI if they do not require live services or secrets.
- [ ] Add a CI-safe mock Docker smoke job if runtime allows Docker-in-Docker; otherwise document it as a local pre-release verification command.
- [ ] Update `README.md`, `services/api/README.md`, `docs/quality/local-development.md`, and `docs/quality/testing.md` with the corrected runtime setup.
- [ ] Update the review document with a final resolution table mapping each finding to the fixing task/commit.
- [ ] Verification: run the full Python suite, frontend build, frontend unit tests, and the mock compose smoke.

## Verification Commands

Use the repository's configured Python runtime when available; otherwise use `python`.

```powershell
python -m pytest packages/contracts/tests packages/workspace/tests packages/timeline/tests tools/import/tests services/api/tests agent/runtime-adapters/mock/tests agent/runtime-adapters/openhands/tests tests -q
```

```powershell
cd apps\web
npm run build
npm run test:unit
```

```powershell
docker compose config
docker compose up -d --build postgres redis api worker web
docker compose logs --tail 80 api worker web
```

Expected:

- Python tests pass.
- Frontend build and unit tests pass.
- Compose config shows runtime env keys on both `api` and `worker`.
- Mock compose smoke can create a workspace, start a background operation, observe timeline updates, and see workspace files.
- OpenHands full-chain smoke is opt-in and clearly reports skipped/missing configuration instead of silently falling back to mock.

## Rollback Or Recovery Notes

- Keep `DOCAGENT_RUNTIME=mock` as the default safe path while OpenHands configuration is being repaired.
- Introduce schema migrations in small steps; each migration should be reversible or additive.
- If persisted OpenHands resume is not supported by the SDK, persist enough metadata to fail clearly and then use one explicit fallback only: clear stale state, create a new product session, or pin OpenHands execution to the worker that created the runtime session. Never silently fork a second OpenHands conversation under the same product session id.
- If Celery streaming proves too risky in one pass, temporarily set the local dev stack to inline queue for OpenHands and document Celery streaming as the next blocking task. Do not leave the current half-wired state where route code constructs streaming callables that the Celery worker never uses.
- Do not remove existing synchronous adapter methods until streaming worker coverage is stable.

## Open Questions

- Does the current OpenHands Agent Server/SDK support reconnecting to an existing conversation by id across processes? If not, which explicit fallback should be used: fail and clear stale state, create a new product session, or pin OpenHands execution to the worker process that created the session?
- Should chat from `await_outline_approval` preserve that state after the agent responds, or can the agent revise the outline and stay awaiting approval?
- Should manual draft edits during a running operation be blocked entirely, or allowed as explicit interrupts with checkpoint creation?
- Should OpenHands dependencies always be included in the API image, or should the project maintain separate mock-only and OpenHands-capable image targets?
- Can CI run Docker Compose reliably in the target environment, or should compose smoke remain a local required verification?

## Execution Order

1. Phase 1 first: verify the now-partial runtime/env fixes, close path-security and repo-root gaps, and make the Docker configuration contract explicit.
2. Phase 2 second: runtime identity and cancellation are prerequisites for trustworthy background work.
3. Phase 3 third: streaming/status events depend on the background lifecycle.
4. Phase 4 fourth: frontend behavior should be fixed once backend semantics are stable.
5. Phase 5 fifth: performance/data-shape hardening (security was addressed in Phase 1) can land independently but should not block the runtime chain.
6. Phase 6 last: docs and smoke tests should reflect the repaired behavior, not the broken current path.
