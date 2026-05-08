# Pre-Assistant-UI Prerequisites: M9 + M4 + M5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add E2E core-loop regression tests, replace 1.5s timeline polling with SSE, and add URL-based deep-linking — enabling safe refactoring during the upcoming assistant-ui integration sprint.

**Architecture:** Three independent improvements applied in order: (1) Playwright tests cover the full authoring loop against the mock adapter with no app code changes; (2) a new FastAPI SSE endpoint replaces client-side polling with a server-push stream using `StreamingResponse` + `EventSource`; (3) `react-router-dom` v7 + search-param sync lets users share direct links to any task/session.

**Tech Stack:** Playwright, FastAPI StreamingResponse (SSE), Browser EventSource API, react-router-dom v7

---

## Files Overview

### M9 — E2E Core Loop Tests
- **Create:** `apps/web/tests/core-loop.spec.ts`

### M4 — SSE Timeline Transport
- **Modify:** `services/api/docagent_api/routes/sessions.py` — add `GET /sessions/{id}/timeline/stream`
- **Create:** `services/api/tests/test_sse.py` — backend unit tests
- **Modify:** `apps/web/src/api.ts` — export `streamTimelineUrl`
- **Modify:** `apps/web/src/shell/state/useTimeline.ts` — replace `setInterval` with EventSource + polling fallback
- **Modify:** `apps/web/src/shell/__tests__/useTimeline.test.tsx` — add EventSource coverage

### M5 — Client-side Routing
- **Modify:** `apps/web/package.json` — add react-router-dom
- **Modify:** `apps/web/src/main.tsx` — wrap with BrowserRouter
- **Modify:** `apps/web/src/App.tsx` — add Routes
- **Modify:** `apps/web/src/shell/state/useWorkspaces.ts` — accept `initialTaskId` / `initialSessionId`
- **Modify:** `apps/web/src/shell/AppShell.tsx` — read URL params on mount, sync URL on selection
- **Modify:** `apps/web/src/shell/__tests__/AppShell.test.tsx` — wrap renders with MemoryRouter
- **Modify:** `apps/web/tests/workbench-shell.spec.ts` — add deep-link E2E test

---

## Task 1: E2E — Start Loop → Outline Card

**Files:**
- Create: `apps/web/tests/core-loop.spec.ts`

- [ ] **Step 1: Create the spec file with workspace setup helper**

```typescript
// apps/web/tests/core-loop.spec.ts
import { expect, test, type Page } from "@playwright/test";

async function createWorkspace(page: Page): Promise<{ title: string }> {
  const title = `Loop E2E ${Date.now()}`;
  await page.goto("/");

  await page
    .locator(".pane-header")
    .filter({ hasText: "Workspaces" })
    .getByRole("button", { name: /create workspace/i })
    .click();

  await page.getByLabel(/title/i).fill(title);
  await page.getByLabel(/description/i).fill("E2E test workspace for core loop.");
  await page
    .locator("form")
    .filter({ has: page.getByLabel(/description/i) })
    .getByRole("button", { name: /^create workspace$/i })
    .click();

  // Workspace creation auto-creates a session — wait for the workspace name to appear
  await expect(page.getByText(title).first()).toBeVisible();
  return { title };
}
```

- [ ] **Step 2: Add the start-loop test**

```typescript
test("start loop produces outline card", async ({ page }) => {
  await createWorkspace(page);

  const composer = page.getByLabel("Message");
  await composer.fill("/start");
  await composer.press("Enter");

  // Mock adapter is synchronous; events arrive within 1.5s poll interval
  await expect(page.getByText("Outline · waiting for review")).toBeVisible({ timeout: 8_000 });
  await expect(page.getByRole("button", { name: /approve/i })).toBeVisible();
});
```

- [ ] **Step 3: Run the test (requires both servers running)**

```bash
cd apps/web && npx playwright test core-loop.spec.ts --headed
```
Expected: PASS — outline card visible within 8s.

- [ ] **Step 4: Commit**

```bash
git add apps/web/tests/core-loop.spec.ts
git commit -m "test(e2e): start loop shows outline card"
```

---

## Task 2: E2E — Outline Approve → Draft Content

**Files:**
- Modify: `apps/web/tests/core-loop.spec.ts`

- [ ] **Step 1: Add the approve → draft test**

```typescript
test("approve outline makes draft content visible", async ({ page }) => {
  await createWorkspace(page);

  const composer = page.getByLabel("Message");
  await composer.fill("/start");
  await composer.press("Enter");

  await expect(page.getByText("Outline · waiting for review")).toBeVisible({ timeout: 8_000 });
  await page.getByRole("button", { name: /approve/i }).click();

  // Mock adapter generates a draft with heading "PRD Draft"
  await expect(page.getByText("PRD Draft")).toBeVisible({ timeout: 8_000 });
});
```

- [ ] **Step 2: Run the new test**

```bash
cd apps/web && npx playwright test core-loop.spec.ts -k "approve outline" --headed
```
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add apps/web/tests/core-loop.spec.ts
git commit -m "test(e2e): approve outline makes draft content visible"
```

---

## Task 3: E2E — Checklist + Export

**Files:**
- Modify: `apps/web/tests/core-loop.spec.ts`

- [ ] **Step 1: Add a shared helper that reaches draft-ready state**

```typescript
async function reachDraftReady(page: Page) {
  await createWorkspace(page);
  const composer = page.getByLabel("Message");
  await composer.fill("/start");
  await composer.press("Enter");
  await expect(page.getByText("Outline · waiting for review")).toBeVisible({ timeout: 8_000 });
  await page.getByRole("button", { name: /approve/i }).click();
  await expect(page.getByText("PRD Draft")).toBeVisible({ timeout: 8_000 });
}
```

- [ ] **Step 2: Add the checklist test**

```typescript
test("run checklist shows checklist card", async ({ page }) => {
  await reachDraftReady(page);

  const composer = page.getByLabel("Message");
  await composer.fill("/check");
  await composer.press("Enter");

  await expect(page.getByText(/checklist · succeeded/i)).toBeVisible({ timeout: 8_000 });
});
```

- [ ] **Step 3: Add the export test**

```typescript
test("export markdown shows artifact card", async ({ page }) => {
  await reachDraftReady(page);

  const composer = page.getByLabel("Message");
  await composer.fill("/export");
  await composer.press("Enter");

  await expect(page.getByText(/artifact · artifacts\/prd-draft\.md/i)).toBeVisible({ timeout: 8_000 });
});
```

- [ ] **Step 4: Run all core-loop tests**

```bash
cd apps/web && npx playwright test core-loop.spec.ts --headed
```
Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/web/tests/core-loop.spec.ts
git commit -m "test(e2e): add checklist and export E2E tests — M9 complete"
```

---

## Task 4: SSE — Backend Streaming Endpoint

**Files:**
- Create: `services/api/tests/test_sse.py`
- Modify: `services/api/docagent_api/routes/sessions.py`

- [ ] **Step 1: Write the failing tests**

```python
# services/api/tests/test_sse.py
from pathlib import Path

from fastapi.testclient import TestClient

from docagent_api.app import create_app


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))


def test_stream_timeline_unknown_session_returns_404(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.get("/sessions/no-such-session/timeline/stream")
    assert response.status_code == 404


def test_stream_timeline_returns_sse_content_type(tmp_path: Path) -> None:
    client = _client(tmp_path)
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "SSE test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    with client.stream("GET", f"/sessions/{session['id']}/timeline/stream") as r:
        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]
        first = next(r.iter_bytes(chunk_size=64))
        assert b":" in first  # SSE comment (keep-alive) starts with ":"


def test_stream_timeline_sends_existing_events(tmp_path: Path) -> None:
    import json

    client = _client(tmp_path)
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "SSE events test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    session_id = session["id"]

    # Run start_loop synchronously to populate the timeline
    client.post(f"/sessions/{session_id}/loop/start")

    data_lines: list[str] = []
    with client.stream("GET", f"/sessions/{session_id}/timeline/stream") as r:
        assert r.status_code == 200
        for line in r.iter_lines():
            line = line.strip()
            if line.startswith("data:"):
                data_lines.append(line[len("data:"):].strip())
            if len(data_lines) >= 1:
                break

    assert data_lines, "expected at least one data line"
    event = json.loads(data_lines[0])
    assert "id" in event
    assert "kind" in event
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd services/api && python -m pytest tests/test_sse.py -v
```
Expected: all 3 tests fail (endpoint does not exist yet).

- [ ] **Step 3: Add imports to sessions.py**

At the top of `services/api/docagent_api/routes/sessions.py`, add after the existing imports:

```python
import asyncio
import json as _json

from fastapi.responses import StreamingResponse
```

- [ ] **Step 4: Add the SSE endpoint in sessions.py**

Inside `create_sessions_router`, immediately before `return router`, add:

```python
    @router.get("/sessions/{session_id}/timeline/stream")
    async def stream_timeline_sse(session_id: str) -> StreamingResponse:
        if state.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found")

        async def generate():
            sent = 0
            yield ": keep-alive\n\n"
            while True:
                events = state.list_timeline_events(session_id)
                for event in events[sent:]:
                    yield f"data: {_json.dumps(event)}\n\n"
                sent = len(events)
                await asyncio.sleep(0.2)

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
```

- [ ] **Step 5: Run SSE tests**

```bash
cd services/api && python -m pytest tests/test_sse.py -v
```
Expected: all 3 pass.

- [ ] **Step 6: Run the full Python test suite**

```bash
cd services/api && python -m pytest -v
```
Expected: all tests pass (87+ previously passing + 3 new).

- [ ] **Step 7: Commit**

```bash
git add services/api/docagent_api/routes/sessions.py services/api/tests/test_sse.py
git commit -m "feat: add SSE timeline stream endpoint GET /sessions/{id}/timeline/stream"
```

---

## Task 5: SSE — Frontend EventSource in useTimeline

**Files:**
- Modify: `apps/web/src/api.ts`
- Modify: `apps/web/src/shell/state/useTimeline.ts`
- Modify: `apps/web/src/shell/__tests__/useTimeline.test.tsx`

- [ ] **Step 1: Export the stream URL from api.ts**

In `apps/web/src/api.ts`, add after the `API_BASE` constant:

```typescript
export const streamTimelineUrl = (sessionId: string): string =>
  `${API_BASE}/sessions/${sessionId}/timeline/stream`;
```

- [ ] **Step 2: Add EventSource tests to useTimeline.test.tsx**

The test environment is jsdom, which does not implement `EventSource`. When `EventSource` is undefined the hook falls back to polling — so existing polling tests continue to work without changes. Add these two new tests inside the existing `describe("useTimeline", ...)` block:

```typescript
  it("opens EventSource for the timeline/stream URL when available", () => {
    const openedUrls: string[] = [];
    const mockClose = vi.fn();

    class MockEventSource {
      onmessage: ((ev: MessageEvent) => void) | null = null;
      onerror: ((ev: Event) => void) | null = null;
      close = mockClose;
      constructor(url: string) {
        openedUrls.push(url);
      }
    }

    vi.stubGlobal("EventSource", MockEventSource);

    let latest!: ReturnType<typeof useTimeline>;
    const { unmount } = render(
      <Harness sessionId="session-sse" onState={(s) => (latest = s)} />
    );

    expect(openedUrls.some((u) => u.includes("/sessions/session-sse/timeline/stream"))).toBe(true);

    unmount();
    expect(mockClose).toHaveBeenCalled();

    vi.unstubAllGlobals();
  });

  it("delivers SSE events into the timeline state via mergeTimelineEvents", async () => {
    let capturedOnMessage: ((ev: MessageEvent) => void) | null = null;
    const mockClose = vi.fn();

    class MockEventSource {
      onmessage: ((ev: MessageEvent) => void) | null = null;
      onerror: ((ev: Event) => void) | null = null;
      close = mockClose;
      constructor(_url: string) {
        // Capture the onmessage setter so we can fire events
        Object.defineProperty(this, "onmessage", {
          set(fn: (ev: MessageEvent) => void) { capturedOnMessage = fn; },
          get() { return capturedOnMessage; },
        });
      }
    }

    vi.stubGlobal("EventSource", MockEventSource);

    const sseEvent: TimelineEvent = {
      id: "sse-event-1",
      actor: "agent",
      kind: "update_draft",
      paths: ["draft/draft.md"],
      status: "succeeded",
      summary: "SSE delivered",
    };

    let latest!: ReturnType<typeof useTimeline>;
    render(<Harness sessionId="session-sse-2" onState={(s) => (latest = s)} />);

    // Fire a simulated SSE message
    act(() => {
      capturedOnMessage?.({ data: JSON.stringify(sseEvent) } as MessageEvent);
    });

    await waitFor(() =>
      expect(latest.events.some((e) => e.id === "sse-event-1")).toBe(true)
    );

    vi.unstubAllGlobals();
  });
```

- [ ] **Step 3: Run unit tests to confirm the new tests fail (EventSource not yet wired)**

```bash
cd apps/web && npm run test:unit -- --reporter=verbose 2>&1 | grep -E "useTimeline|PASS|FAIL"
```
Expected: the two new EventSource tests fail; existing tests still pass.

- [ ] **Step 4: Replace the polling `useEffect` in useTimeline.ts**

Add this import at the top of `useTimeline.ts` (if not already present):

```typescript
import { mergeTimelineEvents, replaceWithIdDedup } from "../conversation/docagentRuntime";
import { streamTimelineUrl } from "../../api";
```

Replace the second `useEffect` (lines 47–64, the `setInterval` block) with:

```typescript
  useEffect(() => {
    if (!sessionId) return;
    const currentSessionId = sessionId;
    let cancelled = false;
    let clearPolling: (() => void) | undefined;

    if (typeof EventSource !== "undefined") {
      const source = new EventSource(streamTimelineUrl(currentSessionId));

      source.onmessage = (ev: MessageEvent) => {
        if (cancelled) return;
        try {
          const event = JSON.parse(ev.data as string) as TimelineEvent;
          setEvents((prev) => mergeTimelineEvents(prev, [event]));
        } catch {
          // ignore unparseable frames (keep-alive comments are filtered by the browser)
        }
      };

      source.onerror = () => {
        source.close();
        if (!cancelled) clearPolling = startPolling(currentSessionId);
      };

      return () => {
        cancelled = true;
        source.close();
        clearPolling?.();
      };
    }

    clearPolling = startPolling(currentSessionId);
    return () => {
      cancelled = true;
      clearPolling?.();
    };

    function startPolling(sid: string) {
      const id = window.setInterval(() => {
        void api.getTimeline(sid)
          .then((nextEvents) => {
            if (!cancelled) setEvents(replaceWithIdDedup(nextEvents));
          })
          .catch((caught) => {
            if (!cancelled) setError(caught instanceof Error ? caught.message : "Could not refresh timeline");
          });
      }, TIMELINE_POLL_INTERVAL_MS);
      return () => window.clearInterval(id);
    }
  }, [sessionId]);
```

- [ ] **Step 5: Run unit tests**

```bash
cd apps/web && npm run test:unit
```
Expected: all tests pass (existing polling tests still pass because jsdom has no `EventSource`; the two new tests now pass).

- [ ] **Step 6: Run E2E core-loop tests — events now arrive within ~200ms instead of ~1500ms**

```bash
cd apps/web && npx playwright test core-loop.spec.ts
```
Expected: all 4 tests pass.

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/api.ts apps/web/src/shell/state/useTimeline.ts apps/web/src/shell/__tests__/useTimeline.test.tsx
git commit -m "feat: replace timeline polling with EventSource SSE (polling fallback preserved) — M4 complete"
```

---

## Task 6: Routing — Install react-router-dom + BrowserRouter

**Files:**
- Modify: `apps/web/package.json`
- Modify: `apps/web/src/main.tsx`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/shell/__tests__/AppShell.test.tsx`

- [ ] **Step 1: Install react-router-dom**

```bash
cd apps/web && npm install react-router-dom@^7
```

- [ ] **Step 2: Replace main.tsx with BrowserRouter wrapper**

```typescript
// apps/web/src/main.tsx
import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
```

- [ ] **Step 3: Replace App.tsx with a Routes wrapper**

```typescript
// apps/web/src/App.tsx
import { Route, Routes } from "react-router-dom";
import { AppShell } from "./shell/AppShell";

export function App() {
  return (
    <Routes>
      <Route path="*" element={<AppShell />} />
    </Routes>
  );
}
```

- [ ] **Step 4: Run type-check**

```bash
cd apps/web && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 5: Run unit tests — expect AppShell tests to fail (missing router context)**

```bash
cd apps/web && npm run test:unit
```
Expected: `AppShell.test.tsx` tests fail with "useSearchParams / useNavigate requires a router context" (or similar). All other tests pass.

- [ ] **Step 6: Wrap every `render(<AppShell />)` in AppShell.test.tsx with MemoryRouter**

Add this import at the top of `apps/web/src/shell/__tests__/AppShell.test.tsx`:

```typescript
import { MemoryRouter } from "react-router-dom";
```

Replace all occurrences of `render(<AppShell />)` with:

```typescript
render(
  <MemoryRouter>
    <AppShell />
  </MemoryRouter>
);
```

There are 7 occurrences on lines 81, 134, 161 (after listTasks mock), 180 (after createTask mock), 198 (after session mock), 248 (settings test), 258 (source editor test), 266 (chat message test). Replace all of them.

- [ ] **Step 7: Run unit tests**

```bash
cd apps/web && npm run test:unit
```
Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add apps/web/package.json apps/web/package-lock.json apps/web/src/main.tsx apps/web/src/App.tsx apps/web/src/shell/__tests__/AppShell.test.tsx
git commit -m "feat: add react-router-dom v7 BrowserRouter foundation (M5 step 1)"
```

---

## Task 7: Routing — URL Param Sync

**Files:**
- Modify: `apps/web/src/shell/state/useWorkspaces.ts`
- Modify: `apps/web/src/shell/AppShell.tsx`
- Modify: `apps/web/tests/workbench-shell.spec.ts`

- [ ] **Step 1: Add initial ID params to useWorkspaces**

In `apps/web/src/shell/state/useWorkspaces.ts`, change the function signature and capture the params in refs so they do not re-trigger `loadInitialState` on URL changes:

```typescript
// Add useRef to the existing import
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
```

Change the function signature from:

```typescript
export function useWorkspaces() {
```

to:

```typescript
export function useWorkspaces(
  initialTaskId?: string | null,
  initialSessionId?: string | null,
) {
  const initialTaskIdRef = useRef(initialTaskId);
  const initialSessionIdRef = useRef(initialSessionId);
```

In `loadInitialState`, replace the two `window.localStorage.getItem` calls with:

```typescript
      // URL params take precedence over localStorage
      const rememberedTaskId =
        initialTaskIdRef.current ?? window.localStorage.getItem(LAST_TASK_KEY);
```

and:

```typescript
        const rememberedSessionId =
          initialSessionIdRef.current ?? window.localStorage.getItem(LAST_SESSION_KEY);
```

Keep `loadInitialState`'s dependency array as `[refreshWorkspaceForTask]` — the refs are stable and do not belong there.

- [ ] **Step 2: Run type-check**

```bash
cd apps/web && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Add URL param sync to AppShell.tsx**

Add these imports to `AppShell.tsx`:

```typescript
import { useRef } from "react";
import { useSearchParams } from "react-router-dom";
```

At the very top of the `AppShell` function body, before the existing `useState` calls, add:

```typescript
  const [searchParams, setSearchParams] = useSearchParams();
  // Capture initial URL params only once — useRef prevents re-running loadInitialState on URL changes
  const initialTaskId = useRef(searchParams.get("task")).current;
  const initialSessionId = useRef(searchParams.get("session")).current;
```

Change the `useWorkspaces()` call to pass the initial IDs:

```typescript
  const workspaces = useWorkspaces(initialTaskId, initialSessionId);
```

Add this URL-sync effect immediately after the existing `useEffect` blocks (before `return`):

```typescript
  // Sync URL params when the active task or session changes
  useEffect(() => {
    const params: Record<string, string> = {};
    if (workspaces.activeTask) params.task = workspaces.activeTask.id;
    if (workspaces.activeSession) params.session = workspaces.activeSession.id;
    setSearchParams(params, { replace: true });
  }, [workspaces.activeTask?.id, workspaces.activeSession?.id, setSearchParams]);
```

- [ ] **Step 4: Run type-check**

```bash
cd apps/web && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 5: Run unit tests**

```bash
cd apps/web && npm run test:unit
```
Expected: all tests pass.

- [ ] **Step 6: Add the deep-link E2E test**

In `apps/web/tests/workbench-shell.spec.ts`, add after the existing two tests:

```typescript
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

  // URL should now contain task= and session= params
  const url = page.url();
  expect(url).toContain("task=");
  expect(url).toContain("session=");

  // Navigate directly to the captured URL — simulates a shared deep link
  await page.goto(url);
  await expect(page.getByText(title).first()).toBeVisible({ timeout: 5_000 });
});
```

- [ ] **Step 7: Run the E2E test**

```bash
cd apps/web && npx playwright test workbench-shell.spec.ts --headed
```
Expected: all 3 tests (2 existing + 1 new deep-link) pass.

- [ ] **Step 8: Run full E2E suite**

```bash
cd apps/web && npx playwright test
```
Expected: all tests pass.

- [ ] **Step 9: Final commit**

```bash
git add apps/web/src/shell/state/useWorkspaces.ts apps/web/src/shell/AppShell.tsx apps/web/tests/workbench-shell.spec.ts
git commit -m "feat: URL deep-linking for task/session selection via search params — M5 complete"
```

---

## Self-Review

**Spec coverage:**
- M9: start loop → outline card (Task 1), approve → draft (Task 2), checklist (Task 3), export (Task 3). All four E2E scenarios covered.
- M4: backend SSE endpoint with 404/headers/data tests (Task 4), frontend EventSource + polling fallback + delivery unit tests (Task 5).
- M5: router install (Task 6), URL sync + deep-link E2E test (Task 7).

**Placeholder scan:** All steps contain complete code. No TBDs.

**Type consistency:**
- `streamTimelineUrl` exported from `api.ts` and imported in `useTimeline.ts`.
- `mergeTimelineEvents` imported from `docagentRuntime.ts` (already exists in that file).
- `useWorkspaces(initialTaskId, initialSessionId)` signature matches call site in `AppShell.tsx`.
- `MemoryRouter` from `react-router-dom` wraps all `<AppShell />` renders in unit tests.

---

**Plan complete and saved to `docs/superpowers/completed/2026-05-07-m9-m4-m5-prerequisites.md`.**

**Two execution options:**

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
