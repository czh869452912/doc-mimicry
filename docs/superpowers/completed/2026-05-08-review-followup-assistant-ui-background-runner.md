# Review Follow-up: Assistant UI And Background Runner Implementation Plan

> **Archive note (2026-05-17):** This completed plan preserves its original
> execution checklist for historical traceability. Any unchecked boxes below are
> not active work; use active plan/review directories for current tasks.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the actionable review follow-ups that remain after excluding DOCX export and PRD seed resources: restore frontend dependency/build baseline, complete task/session deep-linking, add an assistant-ui message-model preparation boundary, and replace ad hoc daemon-thread usage with a managed background runner abstraction.

**Architecture:** Keep the current FastAPI route modules, file-backed state, SSE timeline stream, slash-command adapter, and timeline presentation model. Add a thin assistant-ui boundary around existing semantic timeline events rather than changing backend event contracts. Add a backend `BackgroundRuntimeRunner` abstraction first, backed by in-process threads for Phase 0 but no longer launched as raw daemon threads from route helpers.

**Tech Stack:** React 19, react-router-dom 7, @assistant-ui/react 0.12.28, Vitest, Playwright, FastAPI, Python threading/concurrent futures, existing `DocAgentState` JSON storage.

---

## Scope

Included:

- Restore local frontend dependencies with `npm install` or `npm ci` so package-lock, node_modules, build, and unit tests agree.
- Finish M5 deep-linking so `?task=...&session=...` restores the intended task/session and updates when selection changes.
- Add assistant-ui preparation with the smallest useful adapter boundary: map existing `Presentation` message objects into assistant-ui message model types and preserve slash commands plus existing custom cards. Full assistant-ui runtime/primitive replacement remains future work.
- Replace direct `Thread(..., daemon=True).start()` usage with a `BackgroundRuntimeRunner` service owned by the API factory.
- Update tests and review docs to reflect actual completion state.

Out of scope for this plan:

- DOCX/PDF export implementation.
- Real PRD examples/specs content.
- Assistant-ui advanced Phase B features such as message branching, full tool-call cards, attachments, dictation, and SelectionToolbar.
- Durable cross-process job recovery with Celery/RQ/database queues. This plan removes raw daemon-thread usage and centralizes lifecycle, but it does not claim distributed reliability.

---

## File Map

- Modify: `apps/web/package.json`
- Modify: `apps/web/package-lock.json`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/main.tsx`
- Modify: `apps/web/src/shell/AppShell.tsx`
- Modify: `apps/web/src/shell/state/useWorkspaces.ts`
- Modify: `apps/web/src/shell/panes/ConversationPane.tsx`
- Modify: `apps/web/src/shell/theme/assistant-ui.css`
- Modify: `apps/web/src/shell/__tests__/AppShell.test.tsx`
- Modify: `apps/web/src/shell/__tests__/useWorkspaces.test.tsx`
- Modify: `apps/web/tests/workbench-shell.spec.ts`
- Create: `services/api/docagent_api/background.py`
- Modify: `services/api/docagent_api/app.py`
- Modify: `services/api/docagent_api/routes/_shared.py`
- Modify: `services/api/docagent_api/routes/sessions.py`
- Create or modify: `services/api/tests/test_background_runner.py`
- Modify: `services/api/tests/test_api.py`
- Modify: `docs/reviews/completed/2026-05-07-project-review-assistant-ui-integration.md`

---

### Task 1: Restore Frontend Dependency Baseline

**Files:**
- Modify: `apps/web/package-lock.json`
- Verify: `apps/web/node_modules/`

- [ ] **Step 1: Install dependencies from the committed lockfile**

Run:

```powershell
cd apps\web
npm install
```

Expected:

- `node_modules/react-router-dom`
- `node_modules/react-hook-form`
- `node_modules/@hookform/resolvers`
- `node_modules/react-diff-viewer-continued`
- `node_modules/@assistant-ui/react`

- [ ] **Step 2: Verify the previously failing imports resolve**

Run:

```powershell
cd apps\web
npm run build
```

Expected: PASS.

- [ ] **Step 3: Run frontend unit tests**

Run:

```powershell
cd apps\web
npm run test:unit
```

Expected: PASS. If failures remain after dependency install, treat them as real code issues in later tasks, not environment issues.

- [ ] **Step 4: Check dependency file changes**

Run:

```powershell
git diff -- apps/web/package.json apps/web/package-lock.json
```

Expected: no unintended package version churn. If `package-lock.json` changes only because it was generated on another machine with the same semver ranges, review the diff and keep it if it is deterministic.

---

### Task 2: Finish Task/Session Deep-Linking

**Files:**
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/main.tsx`
- Modify: `apps/web/src/shell/AppShell.tsx`
- Modify: `apps/web/src/shell/state/useWorkspaces.ts`
- Modify: `apps/web/src/shell/__tests__/AppShell.test.tsx`
- Modify: `apps/web/src/shell/__tests__/useWorkspaces.test.tsx`
- Modify: `apps/web/tests/workbench-shell.spec.ts`

- [ ] **Step 1: Add a regression test for URL restoration**

In `apps/web/src/shell/__tests__/AppShell.test.tsx`, add:

```tsx
it("restores task and session from URL search params", async () => {
  vi.mocked(api.listTasks).mockResolvedValue([
    {
      id: "task-1",
      doc_type_id: "prd",
      brief: "Older task",
      title: "Older task",
      description: "Older task",
      workspace_root: "workspace/task-1",
      created_at: "2026-05-06T08:00:00Z",
      updated_at: "2026-05-06T08:00:00Z",
    },
    {
      id: "task-2",
      doc_type_id: "prd",
      brief: "Linked task",
      title: "Linked task",
      description: "Linked task",
      workspace_root: "workspace/task-2",
      created_at: "2026-05-06T08:00:00Z",
      updated_at: "2026-05-06T09:00:00Z",
    },
  ]);
  vi.mocked(api.listTaskSessions).mockImplementation((taskId) =>
    Promise.resolve(
      taskId === "task-2"
        ? [
            {
              id: "session-2",
              task_id: "task-2",
              status: "draft_ready",
              created_at: "2026-05-06T09:00:00Z",
              updated_at: "2026-05-06T09:00:00Z",
            },
          ]
        : [],
    ),
  );
  vi.mocked(api.getWorkspace).mockResolvedValue({ task_id: "task-2", root: "workspace/task-2", files: [] });
  vi.mocked(api.getDraft).mockResolvedValue({ markdown: "# Linked draft" });

  render(
    <MemoryRouter initialEntries={["/?task=task-2&session=session-2"]}>
      <AppShell />
    </MemoryRouter>,
  );

  expect(await screen.findByText("Linked task")).toBeTruthy();
  expect(await screen.findByRole("heading", { name: "Linked draft" })).toBeTruthy();
  await waitFor(() => expect(api.listTaskSessions).toHaveBeenCalledWith("task-2"));
});
```

- [ ] **Step 2: Add a regression test for URL sync after selection**

In the same file, render with `MemoryRouter`, switch task/session, and assert `window.location.search` is not used directly. Prefer asserting visible state and a wrapper component with `useLocation()`:

```tsx
function LocationProbe({ onChange }: { onChange: (search: string) => void }) {
  const location = useLocation();
  useEffect(() => onChange(location.search), [location.search, onChange]);
  return null;
}
```

Expected assertion:

```tsx
await waitFor(() => expect(searches.at(-1)).toContain("task=task-2"));
await waitFor(() => expect(searches.at(-1)).toContain("session=session-2"));
```

- [ ] **Step 3: Run the focused tests and confirm the current gap**

Run:

```powershell
cd apps\web
npm run test:unit -- src/shell/__tests__/AppShell.test.tsx
```

Expected: tests either fail or expose incomplete URL/session behavior.

- [ ] **Step 4: Implement missing URL restore/sync behavior**

Keep these invariants:

- URL params win over localStorage on initial load.
- Invalid URL params fall back to latest task/session.
- Once initial load finishes, active task/session changes update search params with `{ replace: true }`.
- Rendering `AppShell` without a router should not be supported; tests must use `MemoryRouter`.

If `useWorkspaces(initialTaskId, initialSessionId)` already satisfies part of this, only tighten the missing behavior and tests.

- [ ] **Step 5: Add or update Playwright deep-link coverage**

In `apps/web/tests/workbench-shell.spec.ts`, ensure there is a test that:

```ts
test("URL params deep-link to a task and session on reload", async ({ page }) => {
  const title = `Deep link test ${Date.now()}`;
  await page.goto("/");
  await page
    .locator(".pane-header")
    .filter({ hasText: "Workspaces" })
    .getByRole("button", { name: /create workspace/i })
    .click();
  await page.getByLabel(/title/i).fill(title);
  await page.getByLabel(/description/i).fill("Deep link test workspace.");
  await page
    .locator("form")
    .filter({ has: page.getByLabel(/description/i) })
    .getByRole("button", { name: /^create workspace$/i })
    .click();
  await expect(page.getByText(title).first()).toBeVisible();

  const url = page.url();
  expect(url).toContain("task=");
  expect(url).toContain("session=");

  await page.goto(url);
  await expect(page.getByText(title).first()).toBeVisible({ timeout: 5_000 });
});
```

- [ ] **Step 6: Verify**

Run:

```powershell
cd apps\web
npm run test:unit -- src/shell/__tests__/AppShell.test.tsx src/shell/__tests__/useWorkspaces.test.tsx
npm run build
```

Expected: PASS.

---

### Task 3: Introduce Assistant-UI Message-Model Boundary

**Files:**
- Modify: `apps/web/src/shell/panes/ConversationPane.tsx`
- Modify: `apps/web/src/shell/theme/assistant-ui.css`
- Modify: `apps/web/src/shell/__tests__/AppShell.test.tsx`

- [ ] **Step 1: Inspect installed assistant-ui exports**

Run after Task 1:

```powershell
cd apps\web
node -e "console.log(Object.keys(require('@assistant-ui/react')).sort().join('\n'))"
```

Expected: identify the exact primitive/provider exports available in `@assistant-ui/react@0.12.28`. Use the installed package source and examples as the source of truth.

- [ ] **Step 2: Add a test that proves composer behavior is preserved**

Keep the existing AppShell test:

```tsx
it("sends chat messages in background mode and refreshes timeline immediately", async () => {
  render(<MemoryRouter><AppShell /></MemoryRouter>);

  await screen.findByText("Restored workspace");
  vi.mocked(api.getWorkspace).mockClear();
  vi.mocked(api.getTimeline).mockClear();

  await userEvent.type(screen.getByLabelText("Message"), "Revise the draft");
  await userEvent.keyboard("{Enter}");

  await waitFor(() => expect(api.sendMessage).toHaveBeenCalledWith("session-1", "Revise the draft"));
  expect(api.getTimeline).toHaveBeenCalledWith("session-1");
  expect(api.getWorkspace).not.toHaveBeenCalled();
  expect(await screen.findByText("Working...")).toBeTruthy();
});
```

- [ ] **Step 3: Add a test that proves slash commands still work**

Keep or add:

```tsx
it("runs slash commands selected from the command palette", async () => {
  render(<MemoryRouter><AppShell /></MemoryRouter>);

  await screen.findByText("Restored workspace");
  await userEvent.click(screen.getByText("Ctrl K"));
  await userEvent.click(screen.getByText("/help"));

  expect(await screen.findByText("Slash commands")).toBeTruthy();
});
```

- [ ] **Step 4: Add assistant-ui message-model boundary**

Implementation requirements:

- Preserve `ConversationPane` props to avoid changing `AppShell`.
- Preserve `executeSlashCommand`.
- Preserve existing `StreamItem` cards for outline/checklist/artifact/approval.
- Keep `aria-label="Message"` on the composer control so tests and accessibility remain stable.
- Render timeline messages through assistant-ui message/thread primitives only when the installed package exposes React components that can be mounted safely. If the installed API exposes tap resources instead, keep the semantic event rendering local and map timeline messages into assistant-ui message model types as preparation.
- Keep the current composer until a real assistant-ui runtime/composer integration is implemented.

- [ ] **Step 5: Replace CSS override with token mapping**

Update `apps/web/src/shell/theme/assistant-ui.css` from the 5-line font override to a scoped token bridge:

```css
.aui-root,
.aui-thread,
.aui-composer {
  --aui-font-family: var(--font-body);
  --aui-color-background: var(--color-surface);
  --aui-color-foreground: var(--color-ink);
  --aui-color-muted: var(--color-muted);
  --aui-color-border: var(--color-border);
  --aui-color-primary: var(--color-accent);
  font-family: var(--font-body);
}
```

Adjust variable names to match the installed assistant-ui CSS contract after Step 1. Do not invent variables unsupported by the installed package if they have no effect.

- [ ] **Step 6: Verify**

Run:

```powershell
cd apps\web
npm run test:unit -- src/shell/__tests__/AppShell.test.tsx
npm run build
```

Expected: PASS.

---

### Task 4: Add Managed Background Runtime Runner

**Files:**
- Create: `services/api/docagent_api/background.py`
- Modify: `services/api/docagent_api/app.py`
- Modify: `services/api/docagent_api/routes/_shared.py`
- Modify: `services/api/docagent_api/routes/sessions.py`
- Create: `services/api/tests/test_background_runner.py`
- Modify: `services/api/tests/test_api.py`

- [ ] **Step 1: Write runner tests**

Create `services/api/tests/test_background_runner.py`:

```python
from __future__ import annotations

from threading import Event

from docagent_api.background import BackgroundRuntimeRunner


def test_background_runner_completes_submitted_work() -> None:
    runner = BackgroundRuntimeRunner(max_workers=1)
    completed = Event()

    runner.submit("session-1", lambda: completed.set())

    assert completed.wait(timeout=2)
    runner.shutdown()


def test_background_runner_tracks_running_session_ids() -> None:
    runner = BackgroundRuntimeRunner(max_workers=1)
    release = Event()

    runner.submit("session-1", lambda: release.wait(timeout=2))

    assert "session-1" in runner.running_session_ids()
    release.set()
    runner.shutdown()
```

- [ ] **Step 2: Run focused tests and confirm failure**

Run:

```powershell
.local\dev\.venv\Scripts\python.exe -m pytest services/api/tests/test_background_runner.py -q
```

Expected: FAIL because `docagent_api.background` does not exist.

- [ ] **Step 3: Implement `BackgroundRuntimeRunner`**

Create `services/api/docagent_api/background.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from threading import RLock


class BackgroundRuntimeRunner:
    def __init__(self, max_workers: int = 4) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="docagent-runtime")
        self._lock = RLock()
        self._running: dict[str, Future[None]] = {}

    def submit(self, session_id: str, operation: Callable[[], None]) -> Future[None]:
        def wrapped() -> None:
            try:
                operation()
            finally:
                with self._lock:
                    self._running.pop(session_id, None)

        future = self._executor.submit(wrapped)
        with self._lock:
            self._running[session_id] = future
        return future

    def running_session_ids(self) -> set[str]:
        with self._lock:
            return set(self._running)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=False)
```

- [ ] **Step 4: Inject runner from `create_app`**

In `services/api/docagent_api/app.py`, create one runner per app:

```python
from docagent_api.background import BackgroundRuntimeRunner
```

```python
    runner = BackgroundRuntimeRunner()
```

Register shutdown:

```python
    @app.on_event("shutdown")
    def shutdown_background_runner() -> None:
        runner.shutdown()
```

Pass it into session routes:

```python
    app.include_router(create_sessions_router(state, adapter, runner))
```

- [ ] **Step 5: Update route helper signature**

In `services/api/docagent_api/routes/_shared.py`, remove:

```python
from threading import Thread
```

Import:

```python
from docagent_api.background import BackgroundRuntimeRunner
```

Change `start_background_runtime_operation` signature to accept `runner: BackgroundRuntimeRunner`.

Replace:

```python
    Thread(target=worker, daemon=True).start()
```

with:

```python
    runner.submit(session["id"], worker)
```

- [ ] **Step 6: Thread runner through `sessions.py`**

Change:

```python
def create_sessions_router(state: DocAgentState, adapter: Any) -> APIRouter:
```

to:

```python
def create_sessions_router(state: DocAgentState, adapter: Any, runner: BackgroundRuntimeRunner) -> APIRouter:
```

Every call to `start_background_runtime_operation(...)` must pass `runner=runner`.

- [ ] **Step 7: Verify no raw daemon thread remains in API routes**

Run:

```powershell
Select-String -Path 'services\api\docagent_api\**\*.py' -Pattern 'daemon=True|Thread\('
```

Expected: no matches in `services/api/docagent_api/routes/_shared.py` or `routes/sessions.py`.

- [ ] **Step 8: Run backend tests**

Run:

```powershell
.local\dev\.venv\Scripts\python.exe -m pytest services/api/tests/test_background_runner.py services/api/tests/test_api.py services/api/tests/test_sse.py -q
```

Expected: PASS.

---

### Task 5: Update Review Tracking Document

**Files:**
- Modify: `docs/reviews/completed/2026-05-07-project-review-assistant-ui-integration.md`

- [ ] **Step 1: Update status language**

Update the review document so it distinguishes:

- Fixed after review: local dependency baseline restored, M5 deep-linking completed, assistant-ui message-model preparation boundary added, raw daemon-thread route launching removed.
- Still open and intentionally out of scope here: DOCX export, PRD examples/specs.
- Still future work: assistant-ui runtime/primitive integration and Phase B/C advanced features, durable external background job queue.

- [ ] **Step 2: Add verification commands**

Add the exact commands used:

```powershell
.local\dev\.venv\Scripts\python.exe -m pytest -q
cd apps\web
npm run test:unit
npm run build
```

If E2E was run:

```powershell
cd apps\web
npm run test:e2e
```

---

### Task 6: Full Verification

**Files:**
- No code changes expected unless verification exposes a defect.

- [ ] **Step 1: Backend test suite**

Run:

```powershell
.local\dev\.venv\Scripts\python.exe -m pytest -q
```

Expected: PASS.

- [ ] **Step 2: Frontend unit tests**

Run:

```powershell
cd apps\web
npm run test:unit
```

Expected: PASS.

- [ ] **Step 3: Frontend build**

Run:

```powershell
cd apps\web
npm run build
```

Expected: PASS.

- [ ] **Step 4: E2E smoke**

Run if local servers or Playwright webServer config are available:

```powershell
cd apps\web
npm run test:e2e
```

Expected: PASS.

- [ ] **Step 5: Structure check for documentation**

Run:

```powershell
Get-ChildItem -Recurse -File | Select-Object FullName
```

Expected: command completes. Note that local `.venv` output can be large.

- [ ] **Step 6: Git status**

Run:

```powershell
git status --short
```

Expected: only intended tracked changes plus any pre-existing untracked `.claude/`.

---

## Self-Review

Spec coverage:

- Finding 1: handled as environment/dependency restoration, with build/unit verification.
- Finding 2 and Finding 3: explicitly out of scope per user direction.
- Finding 4: assistant-ui Phase A planned with preserved slash commands/cards/tests.
- Finding 5: raw daemon-thread launching replaced with a managed runner abstraction and tests.
- M5 deep-linking: included because the previous review found only a router shell.

Placeholder scan:

- No TBD or deferred implementation steps inside included scope.
- Advanced assistant-ui and durable queue work are explicitly out of scope, not hidden placeholders.

Type consistency:

- Existing `ConversationPane` prop boundary is preserved.
- `BackgroundRuntimeRunner` accepts `session_id` plus a zero-argument operation and returns `Future[None]`.
- `create_sessions_router` receives the runner from `create_app`, matching dependency injection already used for `state` and `adapter`.

---

Plan complete and saved to `docs/superpowers/plans/2026-05-08-review-followup-assistant-ui-background-runner.md`.

Two execution options:

1. Subagent-Driven (recommended) - dispatch a fresh worker per task, review between tasks, fast iteration.
2. Inline Execution - execute tasks in this session using executing-plans, with checkpoints after dependency baseline, assistant-ui, and runner changes.
