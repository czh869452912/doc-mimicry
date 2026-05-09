# State Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `AppShell`'s interval polling and `draftReloadToken` counter with TanStack Router typed search params and TanStack Query server-state hooks, with SSE-driven cache invalidation and exponential backoff reconnect.

**Architecture:** TanStack Router replaces `react-router-dom` for typed URL `?task=` / `?session=` params. TanStack Query replaces all imperative fetch hooks; `useWorkspaces` dissolves into individual Query hooks plus a thin `useActiveWorkspace` URL-state coordinator. `useTimeline` keeps the SSE subscription but calls `queryClient.invalidateQueries` on receipt instead of managing its own polling loop.

**Tech Stack:** React 19, `@tanstack/react-router` v1, `@tanstack/react-query` v5, Vitest, Playwright, FastAPI (unchanged).

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Modify | `apps/web/package.json` | add tanstack deps |
| Modify | `apps/web/src/main.tsx` | RouterProvider + QueryClientProvider |
| Modify | `apps/web/src/App.tsx` | typed route definition + router factory |
| Create | `apps/web/src/shell/state/useTasks.ts` | Query hook `['tasks']` |
| Create | `apps/web/src/shell/state/useSessions.ts` | Query hook `['sessions', taskId]` |
| Create | `apps/web/src/shell/state/useWorkspaceTree.ts` | Query hook `['workspace', taskId]` |
| Create | `apps/web/src/shell/state/useDraft.ts` | Query hook `['draft', taskId]` |
| Create | `apps/web/src/shell/state/useDocTypes.ts` | Query hook `['docTypes']` |
| Create | `apps/web/src/shell/state/useActiveWorkspace.ts` | URL-state coordinator; replaces useWorkspaces |
| Modify | `apps/web/src/shell/state/useTimeline.ts` | add taskId param, remove clear-before-load, SSE invalidation, exponential backoff |
| Modify | `apps/web/src/shell/state/useWorkspaces.ts` | delete (replaced) |
| Modify | `apps/web/src/shell/AppShell.tsx` | use new hooks, remove interval + draftReloadToken |
| Modify | `apps/web/src/types.ts` | add optional `created_at` to `TimelineEvent` |
| Modify | `apps/web/src/shell/assistant/docAgentAssistantMessages.ts` | use real timestamp |
| Modify | `apps/web/src/shell/__tests__/AppShell.test.tsx` | TanStack Router test harness |
| Modify | `apps/web/tests/workbench-shell.spec.ts` | no change expected; verify passes |

---

### Task 1: Install packages and wire provider infrastructure

**Files:**
- Modify: `apps/web/package.json`
- Modify: `apps/web/src/main.tsx`
- Modify: `apps/web/src/App.tsx`

- [x] **Step 1: Install TanStack Router and TanStack Query**

```bash
cd apps/web
npm install @tanstack/react-router @tanstack/react-query
```

Expected: both packages appear in `node_modules/`.

- [x] **Step 2: Define the typed route tree in `App.tsx`**

Replace the entire contents of `apps/web/src/App.tsx`:

```tsx
import { createMemoryHistory, createRootRoute, createRoute, createRouter, Outlet, RouterHistory } from "@tanstack/react-router";
import { AppShell } from "./shell/AppShell";

export type AppSearch = {
  task?: string;
  session?: string;
};

const rootRoute = createRootRoute({
  component: Outlet,
});

export const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  validateSearch: (search: Record<string, unknown>): AppSearch => ({
    task: typeof search.task === "string" ? search.task : undefined,
    session: typeof search.session === "string" ? search.session : undefined,
  }),
  component: AppShell,
});

const routeTree = rootRoute.addChildren([indexRoute]);

export function createAppRouter(history?: RouterHistory) {
  return createRouter({ routeTree, history });
}

declare module "@tanstack/react-router" {
  interface Register {
    router: ReturnType<typeof createAppRouter>;
  }
}
```

- [x] **Step 3: Wire `RouterProvider` and `QueryClientProvider` in `main.tsx`**

Replace the entire contents of `apps/web/src/main.tsx`:

```tsx
import React from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "@tanstack/react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createAppRouter } from "./App";
import "./styles.css";

const queryClient = new QueryClient();
const router = createAppRouter();

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>,
);
```

- [x] **Step 4: Verify build compiles**

```bash
cd apps/web
npm run build
```

Expected: PASS. (AppShell still uses `react-router-dom` imports --that is expected and will be fixed in Task 6. The build succeeds because both libraries coexist temporarily.)

- [x] **Step 5: Commit**

```bash
git add apps/web/package.json apps/web/package-lock.json apps/web/src/main.tsx apps/web/src/App.tsx
git commit -m "feat: install tanstack router + query; wire provider infrastructure"
```

---

### Task 2: Add `created_at` to `TimelineEvent` and use real timestamps

**Files:**
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/shell/assistant/docAgentAssistantMessages.ts`

- [x] **Step 1: Write a failing unit test for timestamp mapping**

In `apps/web/src/shell/assistant/__tests__/docAgentAssistantMessages.test.ts` (create if absent), add:

```ts
import { describe, expect, it } from "vitest";
import { mapTimelineEventsToAssistantMessages } from "../docAgentAssistantMessages";
import type { TimelineEvent } from "../../../types";

describe("mapTimelineEventsToAssistantMessages", () => {
  it("uses created_at when present", () => {
    const event: TimelineEvent = {
      id: "e1",
      actor: "agent",
      kind: "user_message",
      summary: "Hello",
      paths: [],
      status: "done",
      created_at: "2026-05-08T10:00:00Z",
    };
    const [msg] = mapTimelineEventsToAssistantMessages([event]);
    expect(msg.createdAt.toISOString()).toBe("2026-05-08T10:00:00.000Z");
  });

  it("falls back to epoch when created_at is absent", () => {
    const event: TimelineEvent = {
      id: "e2",
      actor: "agent",
      kind: "user_message",
      summary: "Hi",
      paths: [],
      status: "done",
    };
    const [msg] = mapTimelineEventsToAssistantMessages([event]);
    expect(msg.createdAt.getTime()).toBe(0);
  });
});
```

- [x] **Step 2: Run the test to confirm it fails**

```bash
cd apps/web
npm run test:unit -- src/shell/assistant/__tests__/docAgentAssistantMessages.test.ts
```

Expected: FAIL --`TimelineEvent` has no `created_at` property.

- [x] **Step 3: Add `created_at` to `TimelineEvent` in `types.ts`**

In `apps/web/src/types.ts`, change:

```ts
export interface TimelineEvent {
  id: string;
  actor: string;
  kind: string;
  summary: string;
  paths: string[];
  status: string;
}
```

to:

```ts
export interface TimelineEvent {
  id: string;
  actor: string;
  kind: string;
  summary: string;
  paths: string[];
  status: string;
  created_at?: string;
}
```

- [x] **Step 4: Use `created_at` in `mapTimelineEventToAssistantMessage`**

In `apps/web/src/shell/assistant/docAgentAssistantMessages.ts`, change line 38:

```ts
const createdAt = new Date(0);
```

to:

```ts
const createdAt = event.created_at ? new Date(event.created_at) : new Date(0);
```

- [x] **Step 5: Run the test to confirm it passes**

```bash
cd apps/web
npm run test:unit -- src/shell/assistant/__tests__/docAgentAssistantMessages.test.ts
```

Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add apps/web/src/types.ts apps/web/src/shell/assistant/docAgentAssistantMessages.ts apps/web/src/shell/assistant/__tests__/docAgentAssistantMessages.test.ts
git commit -m "feat: add created_at to TimelineEvent; use real timestamps in assistant messages"
```

---

### Task 3: Create individual Query data hooks

**Files:**
- Create: `apps/web/src/shell/state/useDocTypes.ts`
- Create: `apps/web/src/shell/state/useTasks.ts`
- Create: `apps/web/src/shell/state/useSessions.ts`
- Create: `apps/web/src/shell/state/useWorkspaceTree.ts`
- Create: `apps/web/src/shell/state/useDraft.ts`

- [x] **Step 1: Create `useDocTypes.ts`**

```ts
// apps/web/src/shell/state/useDocTypes.ts
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";

export function useDocTypes() {
  return useQuery({
    queryKey: ["docTypes"],
    queryFn: () => api.listDocTypes(),
    staleTime: Infinity,
  });
}
```

- [x] **Step 2: Create `useTasks.ts`**

```ts
// apps/web/src/shell/state/useTasks.ts
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";

export function useTasks() {
  return useQuery({
    queryKey: ["tasks"],
    queryFn: () => api.listTasks(),
    staleTime: 30_000,
  });
}
```

- [x] **Step 3: Create `useSessions.ts`**

```ts
// apps/web/src/shell/state/useSessions.ts
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";

export function useSessions(taskId: string | null | undefined) {
  return useQuery({
    queryKey: ["sessions", taskId],
    queryFn: () => api.listTaskSessions(taskId!),
    enabled: !!taskId,
    staleTime: 10_000,
  });
}
```

- [x] **Step 4: Create `useWorkspaceTree.ts`**

```ts
// apps/web/src/shell/state/useWorkspaceTree.ts
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "../../api";

export function useWorkspaceTree(taskId: string | null | undefined) {
  return useQuery({
    queryKey: ["workspace", taskId],
    queryFn: () => api.getWorkspace(taskId!),
    enabled: !!taskId,
    staleTime: 10_000,
    placeholderData: keepPreviousData,
  });
}
```

- [x] **Step 5: Create `useDraft.ts`**

```ts
// apps/web/src/shell/state/useDraft.ts
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "../../api";

export function useDraft(taskId: string | null | undefined) {
  return useQuery({
    queryKey: ["draft", taskId],
    queryFn: () => api.getDraft(taskId!),
    enabled: !!taskId,
    staleTime: 10_000,
    placeholderData: keepPreviousData,
  });
}
```

- [x] **Step 6: Verify build**

```bash
cd apps/web
npm run build
```

Expected: PASS.

- [x] **Step 7: Commit**

```bash
git add apps/web/src/shell/state/useDocTypes.ts apps/web/src/shell/state/useTasks.ts apps/web/src/shell/state/useSessions.ts apps/web/src/shell/state/useWorkspaceTree.ts apps/web/src/shell/state/useDraft.ts
git commit -m "feat: add individual TanStack Query data hooks for tasks, sessions, workspace, draft"
```

---

### Task 4: Create `useActiveWorkspace` coordinator

**Files:**
- Create: `apps/web/src/shell/state/useActiveWorkspace.ts`

This replaces the selection logic from `useWorkspaces`. It holds active task/session as URL state (not React state), reads initial values from URL params with localStorage fallback, and exposes mutations via `useMutation`.

- [x] **Step 1: Write a failing test**

Create `apps/web/src/shell/state/__tests__/useActiveWorkspace.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { api } from "../../../api";
import { createAppRouter } from "../../../App";

vi.mock("../../../api", () => ({
  api: {
    listDocTypes: vi.fn().mockResolvedValue([]),
    listTasks: vi.fn().mockResolvedValue([
      { id: "t1", doc_type_id: "prd", brief: "Task 1", title: "Task 1", description: "", workspace_root: "w/t1", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
    ]),
    listTaskSessions: vi.fn().mockResolvedValue([
      { id: "s1", task_id: "t1", status: "draft_ready", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" },
    ]),
    getWorkspace: vi.fn().mockResolvedValue({ task_id: "t1", root: "w/t1", files: [] }),
    getDraft: vi.fn().mockResolvedValue({ task_id: "t1", markdown: "" }),
    getTimeline: vi.fn().mockResolvedValue([]),
  },
}));

function renderWithRouter(initialUrl = "/") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createAppRouter(createMemoryHistory({ initialEntries: [initialUrl] }));
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("useActiveWorkspace via AppShell", () => {
  it("restores active task from URL ?task param", async () => {
    renderWithRouter("/?task=t1&session=s1");
    await waitFor(() => expect(api.listTaskSessions).toHaveBeenCalledWith("t1"));
  });
});
```

- [x] **Step 2: Run the test to confirm it fails**

```bash
cd apps/web
npm run test:unit -- src/shell/state/__tests__/useActiveWorkspace.test.tsx
```

Expected: FAIL or error because `useActiveWorkspace` does not exist yet.

- [x] **Step 3: Create `useActiveWorkspace.ts`**

```ts
// apps/web/src/shell/state/useActiveWorkspace.ts
import { useNavigate, useSearch } from "@tanstack/react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef } from "react";
import { api } from "../../api";
import type { SessionRecord, TaskRecord } from "../../types";
import { useDocTypes } from "./useDocTypes";
import { useSessions } from "./useSessions";
import { useTasks } from "./useTasks";

const LAST_TASK_KEY = "docagent:lastTaskId";
const LAST_SESSION_KEY = "docagent:lastSessionId";

export function isRunnableSession(session: SessionRecord): boolean {
  return !["cancelled", "completed", "failed"].includes(session.status);
}

function latestByUpdatedAt<T extends { updated_at: string }>(items: T[]): T | null {
  return [...items].sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at))[0] ?? null;
}

export function useActiveWorkspace() {
  const navigate = useNavigate({ from: "/" });
  const search = useSearch({ from: "/" });
  const queryClient = useQueryClient();

  const docTypesQuery = useDocTypes();
  const tasksQuery = useTasks();
  const tasks = tasksQuery.data ?? [];

  // Active task: resolved from URL param, else null
  const activeTask = tasks.find((t) => t.id === search.task) ?? null;

  const sessionsQuery = useSessions(activeTask?.id);
  const sessions = sessionsQuery.data ?? [];

  // Active session: resolved from URL param, then latest
  const activeSession =
    sessions.find((s) => s.id === search.session) ?? latestByUpdatedAt(sessions) ?? null;

  // Sync URL when session resolves to a default (no explicit URL param)
  useEffect(() => {
    if (!activeSession || activeSession.id === search.session) return;
    void navigate({ search: (prev) => ({ ...prev, session: activeSession.id }), replace: true });
  }, [activeSession?.id, search.session, navigate]);

  // On first load: if no task URL param, navigate to best task from localStorage/latest
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

  const selectTask = useCallback(
    (task: TaskRecord) => {
      window.localStorage.setItem(LAST_TASK_KEY, task.id);
      window.localStorage.removeItem(LAST_SESSION_KEY);
      void navigate({ search: { task: task.id }, replace: true });
    },
    [navigate],
  );

  const selectSession = useCallback(
    (session: SessionRecord) => {
      window.localStorage.setItem(LAST_SESSION_KEY, session.id);
      void navigate({ search: (prev) => ({ ...prev, session: session.id }), replace: true });
    },
    [navigate],
  );

  const createWorkspaceMutation = useMutation({
    mutationFn: async ({ docTypeId, input }: { docTypeId: string; input: { title: string; description: string } }) => {
      const task = await api.createTask(docTypeId, input);
      const session = await api.createSession(task.id);
      return { task, session };
    },
    onSuccess: ({ task, session }) => {
      window.localStorage.setItem(LAST_TASK_KEY, task.id);
      window.localStorage.setItem(LAST_SESSION_KEY, session.id);
      void queryClient.invalidateQueries({ queryKey: ["tasks"] });
      void navigate({ search: { task: task.id, session: session.id }, replace: true });
    },
  });

  const createSessionMutation = useMutation({
    mutationFn: async () => {
      if (!activeTask) throw new Error("No active task");
      return api.createSession(activeTask.id);
    },
    onSuccess: (session) => {
      window.localStorage.setItem(LAST_SESSION_KEY, session.id);
      void queryClient.invalidateQueries({ queryKey: ["sessions", activeTask?.id] });
      void navigate({ search: (prev) => ({ ...prev, session: session.id }), replace: true });
    },
  });

  const ensureSession = useCallback(async (): Promise<SessionRecord | null> => {
    if (!activeTask) return null;
    if (activeSession && isRunnableSession(activeSession)) return activeSession;
    return createSessionMutation.mutateAsync();
  }, [activeTask, activeSession, createSessionMutation]);

  const loading = tasksQuery.isLoading || sessionsQuery.isLoading;
  const error = tasksQuery.error?.message ?? sessionsQuery.error?.message ?? null;

  return {
    activeSession,
    activeTask,
    createWorkspace: (docTypeId: string, input: { title: string; description: string }) =>
      createWorkspaceMutation.mutateAsync({ docTypeId, input }),
    createSessionForActiveTask: () => createSessionMutation.mutateAsync(),
    docTypes: docTypesQuery.data ?? [],
    ensureSession,
    error,
    loading,
    selectSession,
    selectTask,
    sessions,
    tasks,
  };
}
```

- [x] **Step 4: Run the test**

```bash
cd apps/web
npm run test:unit -- src/shell/state/__tests__/useActiveWorkspace.test.tsx
```

Expected: PASS.

- [x] **Step 5: Verify build**

```bash
cd apps/web
npm run build
```

Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add apps/web/src/shell/state/useActiveWorkspace.ts apps/web/src/shell/state/__tests__/useActiveWorkspace.test.tsx
git commit -m "feat: add useActiveWorkspace coordinator with TanStack Router URL state"
```

---

### Task 5: Update `useTimeline` --add `taskId`, remove clear-before-load, add SSE invalidation and exponential backoff

**Files:**
- Modify: `apps/web/src/shell/state/useTimeline.ts`

- [x] **Step 1: Write failing tests for new behavior**

Create `apps/web/src/shell/state/__tests__/useTimeline.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, act } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { useTimeline } from "../useTimeline";
import { api } from "../../../api";

vi.mock("../../../api", () => ({
  api: { getTimeline: vi.fn() },
  streamTimelineUrl: vi.fn().mockReturnValue("http://localhost/stream"),
}));

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("useTimeline", () => {
  beforeEach(() => {
    vi.mocked(api.getTimeline).mockResolvedValue([]);
  });

  it("does not clear events when session changes (keepPreviousData)", async () => {
    vi.mocked(api.getTimeline).mockResolvedValue([
      { id: "e1", actor: "agent", kind: "user_message", summary: "Hi", paths: [], status: "done" },
    ]);
    const { result, rerender } = renderHook(
      ({ sid, tid }) => useTimeline(sid, tid),
      { wrapper, initialProps: { sid: "session-1", tid: "task-1" } },
    );
    // Events loaded
    await vi.waitFor(() => expect(result.current.events).toHaveLength(1));
    // Change session --events must NOT be cleared to empty during refetch
    vi.mocked(api.getTimeline).mockResolvedValue([]);
    rerender({ sid: "session-2", tid: "task-1" });
    // During the brief window before the new fetch resolves, events must not be []
    expect(result.current.events).toHaveLength(1);
  });
});
```

- [x] **Step 2: Run the test to confirm it fails**

```bash
cd apps/web
npm run test:unit -- src/shell/state/__tests__/useTimeline.test.tsx
```

Expected: FAIL because `useTimeline` currently calls `setEvents([])` on session change.

- [x] **Step 3: Rewrite `useTimeline.ts`**

Replace the entire contents of `apps/web/src/shell/state/useTimeline.ts`:

```ts
import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, streamTimelineUrl } from "../../api";
import type { TimelineEvent } from "../../types";
import { mergeTimelineEvents, replaceWithIdDedup } from "../conversation/docagentRuntime";

const TIMELINE_POLL_INTERVAL_MS = 3000;
const SSE_BACKOFF_BASE_MS = 1000;
const SSE_BACKOFF_MAX_MS = 30_000;

export function useTimeline(
  sessionId: string | null | undefined,
  taskId: string | null | undefined,
) {
  const queryClient = useQueryClient();
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  // Keep previous events across session changes --don't clear before new load
  const prevSessionIdRef = useRef<string | null | undefined>(null);

  const loadTimeline = useCallback(
    async (sid: string | null | undefined, shouldApply: () => boolean = () => true) => {
      if (!sid) {
        if (shouldApply()) {
          setEvents([]);
          setError(null);
          setLoading(false);
        }
        return [];
      }
      setLoading(true);
      setError(null);
      // No setEvents([]) here --leave previous events visible during fetch
      try {
        const nextEvents = replaceWithIdDedup(await api.getTimeline(sid));
        if (shouldApply()) setEvents(nextEvents);
        return nextEvents;
      } catch (caught) {
        if (shouldApply())
          setError(caught instanceof Error ? caught.message : "Could not refresh timeline");
        return [];
      } finally {
        if (shouldApply()) setLoading(false);
      }
    },
    [],
  );

  const refreshTimeline = useCallback(
    async () => loadTimeline(sessionId),
    [loadTimeline, sessionId],
  );

  useEffect(() => {
    let cancelled = false;
    void loadTimeline(sessionId, () => !cancelled);
    return () => {
      cancelled = true;
    };
  }, [loadTimeline, sessionId]);

  // SSE subscription with exponential backoff reconnect
  useEffect(() => {
    if (!sessionId) return;
    const currentSessionId = sessionId;
    const currentTaskId = taskId;
    let cancelled = false;
    let pollId: ReturnType<typeof window.setInterval> | undefined;
    let reconnectId: ReturnType<typeof window.setTimeout> | undefined;
    let backoffMs = SSE_BACKOFF_BASE_MS;

    function invalidateRelatedQueries(event: TimelineEvent) {
      void queryClient.invalidateQueries({ queryKey: ["timeline", currentSessionId] });
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
      if (!("EventSource" in window)) {
        startPolling();
        return;
      }
      const source = new EventSource(streamTimelineUrl(currentSessionId));

      source.onmessage = (ev: MessageEvent) => {
        if (cancelled) return;
        backoffMs = SSE_BACKOFF_BASE_MS; // reset on successful message
        try {
          const event = JSON.parse(ev.data as string) as TimelineEvent;
          setEvents((prev) => mergeTimelineEvents(prev, [event]));
          invalidateRelatedQueries(event);
        } catch {
          // ignore unparseable keep-alive frames
        }
      };

      source.onerror = () => {
        source.close();
        if (cancelled) return;
        // Re-fetch timeline to catch up on missed events
        void api.getTimeline(currentSessionId).then((nextEvents) => {
          if (!cancelled) setEvents(replaceWithIdDedup(nextEvents));
        });
        // Reconnect with exponential backoff
        reconnectId = window.setTimeout(() => {
          if (!cancelled) connect();
        }, backoffMs);
        backoffMs = Math.min(backoffMs * 2, SSE_BACKOFF_MAX_MS);
      };

      return () => source.close();
    }

    const cleanup = connect();

    return () => {
      cancelled = true;
      cleanup?.();
      if (pollId !== undefined) window.clearInterval(pollId);
      if (reconnectId !== undefined) window.clearTimeout(reconnectId);
    };
  }, [sessionId, taskId, queryClient]);

  const resetTimeline = useCallback(() => {
    setEvents([]);
    setError(null);
  }, []);

  return { error, events, loading, refreshTimeline, resetTimeline };
}
```

- [x] **Step 4: Run the test**

```bash
cd apps/web
npm run test:unit -- src/shell/state/__tests__/useTimeline.test.tsx
```

Expected: PASS.

- [x] **Step 5: Verify build**

```bash
cd apps/web
npm run build
```

Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add apps/web/src/shell/state/useTimeline.ts apps/web/src/shell/state/__tests__/useTimeline.test.tsx
git commit -m "feat: update useTimeline with SSE invalidation, exponential backoff, no clear-before-load"
```

---

### Task 6: Update `AppShell` to use new hooks --remove interval polling and `draftReloadToken`

**Files:**
- Modify: `apps/web/src/shell/AppShell.tsx`
- Modify (delete): `apps/web/src/shell/state/useWorkspaces.ts`

- [x] **Step 1: Rewrite `AppShell.tsx`**

Replace the entire contents of `apps/web/src/shell/AppShell.tsx`:

```tsx
import { useState } from "react";
import { api } from "../api";
import type { WorkspaceFileContent } from "../types";
import { CommandPalette } from "./CommandPalette";
import { SettingsDrawer } from "./SettingsDrawer";
import { TopBar } from "./TopBar";
import { titleFromPath, tabKindForPath, useTabs } from "./editor/useTabs";
import { EditorPane } from "./panes/EditorPane";
import { ConversationPane } from "./panes/ConversationPane";
import { WorkspacePane } from "./panes/WorkspacePane";
import { useCollapse } from "./state/useCollapse";
import { useTimeline } from "./state/useTimeline";
import { useActiveWorkspace } from "./state/useActiveWorkspace";
import { useWorkspaceTree } from "./state/useWorkspaceTree";
import { useDraft } from "./state/useDraft";
import { buildWorkspaceTreeData } from "./state/useWorkspaces";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "../components/ui/resizable";
import { ErrorBoundary } from "./ErrorBoundary";
import { useQueryClient } from "@tanstack/react-query";

export function AppShell() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [queuedComposerDraft, setQueuedComposerDraft] = useState<string | null>(null);
  const [queuedCommand, setQueuedCommand] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const workspaces = useActiveWorkspace();
  const workspaceTreeQuery = useWorkspaceTree(workspaces.activeTask?.id);
  const draftQuery = useDraft(workspaces.activeTask?.id);
  const editorTabs = useTabs();
  const collapse = useCollapse();
  const timeline = useTimeline(workspaces.activeSession?.id, workspaces.activeTask?.id);

  const draft = draftQuery.data?.markdown ?? "";
  const draftTaskId = draftQuery.data?.task_id ?? null;

  const treeData = buildWorkspaceTreeData(
    workspaces.tasks,
    workspaces.activeTask ? { [workspaces.activeTask.id]: workspaces.sessions } : {},
    workspaces.activeTask && workspaceTreeQuery.data
      ? { [workspaces.activeTask.id]: workspaceTreeQuery.data }
      : {},
  );

  const topBarStatus = workspaces.activeSession?.status?.startsWith("running")
    ? "running"
    : workspaces.activeSession?.status === "failed"
      ? "failed"
      : "idle";

  return (
    <main className="docagent-shell" onKeyDown={handleKeyDown}>
      <TopBar
        workspaceLabel={workspaces.activeTask?.title ?? workspaces.activeTask?.brief ?? "No workspace"}
        sessionLabel={workspaces.activeSession ? `session ${workspaces.activeSession.id.slice(0, 8)}` : "no session"}
        status={topBarStatus}
        onOpenCommandPalette={() => setCommandOpen(true)}
        onOpenSettings={() => setSettingsOpen(true)}
      />
      <ResizablePanelGroup
        orientation="horizontal"
        className="docagent-shell__panels"
        defaultLayout={{ left: collapse.leftPanelSize, center: 100 - collapse.leftPanelSize - collapse.rightPanelSize, right: collapse.rightPanelSize }}
        onLayoutChanged={collapse.rememberLayout}
      >
        <ResizablePanel id="left" defaultSize={collapse.leftPanelSize} minSize={12} collapsedSize={4} collapsible>
          <aside className="shell-panel">
            <ErrorBoundary label="Workspace">
              <WorkspacePane
                activeSession={workspaces.activeSession}
                activeTask={workspaces.activeTask}
                docTypes={workspaces.docTypes}
                error={workspaces.error}
                loading={workspaces.loading}
                nodes={treeData}
                sessions={workspaces.sessions}
                onCreateWorkspace={async (docTypeId, brief) => {
                  await workspaces.createWorkspace(docTypeId, brief);
                }}
                onCreateSession={async () => {
                  await workspaces.createSessionForActiveTask();
                }}
                onOpenFile={(path) => {
                  void openWorkspaceFile(path);
                }}
                onSelectSession={(sessionId) => {
                  const session = workspaces.sessions.find((s) => s.id === sessionId);
                  if (session) workspaces.selectSession(session);
                }}
                onSelectTask={(taskId) => {
                  const task = workspaces.tasks.find((t) => t.id === taskId);
                  if (task) workspaces.selectTask(task);
                }}
              />
            </ErrorBoundary>
          </aside>
        </ResizablePanel>
        <ResizableHandle className="resize-handle" />
        <ResizablePanel id="center" minSize={32}>
          <section className="shell-panel shell-panel--center">
            <ErrorBoundary label="Conversation">
              <ConversationPane
                activeSession={workspaces.activeSession}
                activeTask={workspaces.activeTask}
                ensureSession={workspaces.ensureSession}
                events={timeline.events}
                error={timeline.error}
                loading={timeline.loading}
                onOpenPath={openWorkspaceFile}
                onQueuedComposerDraftHandled={() => setQueuedComposerDraft(null)}
                onQueuedCommandHandled={() => setQueuedCommand(null)}
                queuedComposerDraft={queuedComposerDraft}
                queuedCommand={queuedCommand}
                refreshTimeline={timeline.refreshTimeline}
                refreshWorkspace={async () => {
                  await queryClient.invalidateQueries({ queryKey: ["workspace", workspaces.activeTask?.id] });
                  await queryClient.invalidateQueries({ queryKey: ["draft", workspaces.activeTask?.id] });
                }}
              />
            </ErrorBoundary>
          </section>
        </ResizablePanel>
        <ResizableHandle className="resize-handle" />
        <ResizablePanel id="right" defaultSize={collapse.rightPanelSize} minSize={18} collapsedSize={4} collapsible>
          <aside className="shell-panel">
            <ErrorBoundary label="Editor">
              <EditorPane
                activeSessionId={workspaces.activeSession?.id ?? null}
                activeTabId={editorTabs.activeTabId}
                draft={draft}
                draftAutoSaveEnabled={draftTaskId === (workspaces.activeTask?.id ?? null)}
                tabs={editorTabs.tabs}
                taskId={workspaces.activeTask?.id ?? null}
                onCloseTab={editorTabs.removeTab}
                onDraftChange={() => {}}
                onReviseSelection={reviseSelectedText}
                onSendSelectionToChat={(selectedText) => {
                  setQueuedComposerDraft(selectionPrompt(selectedText));
                }}
                onTabChange={editorTabs.setActiveTabId}
              />
            </ErrorBoundary>
          </aside>
        </ResizablePanel>
      </ResizablePanelGroup>
      <CommandPalette open={commandOpen} onClose={() => setCommandOpen(false)} onRunCommand={setQueuedCommand} />
      <SettingsDrawer
        docTypes={workspaces.docTypes}
        open={settingsOpen}
        runtimeLabel={import.meta.env.VITE_DOCAGENT_RUNTIME ?? "mock"}
        onOpenChange={setSettingsOpen}
      />
    </main>
  );

  function handleKeyDown(event: React.KeyboardEvent) {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      setCommandOpen(true);
    }
  }

  async function openWorkspaceFile(path: string) {
    if (!workspaces.activeTask) return;
    const file = await api.getWorkspaceFile(workspaces.activeTask.id, path);
    editorTabs.openTab(tabFromWorkspaceFile(file));
  }

  async function reviseSelectedText(selectedText: string) {
    if (!workspaces.activeSession) return;
    await api.reviseSelection(
      workspaces.activeSession.id,
      selectedText,
      "Please revise the selected passage while preserving its meaning.",
    );
    await timeline.refreshTimeline();
    await queryClient.invalidateQueries({ queryKey: ["workspace", workspaces.activeTask?.id] });
    await queryClient.invalidateQueries({ queryKey: ["draft", workspaces.activeTask?.id] });
  }
}

function selectionPrompt(selectedText: string) {
  return `Please review this selected passage and suggest improvements:\n\n> ${selectedText}`;
}

function tabFromWorkspaceFile(file: WorkspaceFileContent) {
  const kind = tabKindForPath(file.path);
  const common = { id: `${kind}:${file.path}`, title: titleFromPath(file.path), path: file.path, content: file.content };
  if (kind === "version") return { ...common, kind };
  if (kind === "artifact") return { ...common, kind };
  return { ...common, kind: "file" as const };
}
```

Note: `onDraftChange` is passed as a no-op because `useDraft` now owns draft state. If the editor needs to save drafts, it calls `api.updateDraft` directly --that pattern is unchanged.

- [x] **Step 2: Trim `useWorkspaces.ts` to re-export only the helpers still used by AppShell**

`AppShell` imports `buildWorkspaceTreeData` and `isRunnableSession` from `useWorkspaces`. Keep those exports; delete the rest of the file body.

Replace `apps/web/src/shell/state/useWorkspaces.ts` with:

```ts
// Retained for re-export --migration target: inline callers and delete this file.
export { buildWorkspaceTreeData, isRunnableSession, latestByUpdatedAt } from "./useWorkspaces_helpers";
export type { WorkspaceTreeNode, WorkspaceTreeNodeKind, CreateWorkspaceInput } from "./useWorkspaces_types";
```

Wait --this creates a circular reference. Instead, move just the pure helper functions into a small file.

Replace `apps/web/src/shell/state/useWorkspaces.ts` with only the pure helpers that are still needed:

```ts
// apps/web/src/shell/state/useWorkspaces.ts
// This file retains only the pure helper functions used by AppShell and WorkspacePane.
// The useWorkspaces hook itself has been replaced by useActiveWorkspace + individual Query hooks.

import type { SessionRecord, TaskRecord, WorkspaceFile, WorkspaceTree } from "../../types";

export type WorkspaceTreeNodeKind = "task" | "session" | "folder" | "file";

export interface WorkspaceTreeNode {
  id: string;
  name: string;
  kind: WorkspaceTreeNodeKind;
  taskId?: string;
  sessionId?: string;
  path?: string;
  status?: string;
  children?: WorkspaceTreeNode[];
}

export interface CreateWorkspaceInput {
  description: string;
  title: string;
}

const WORKSPACE_FOLDERS = ["versions", "inputs", "context", "draft", "reviews", "artifacts"] as const;

export function latestByUpdatedAt<T extends { updated_at: string }>(items: T[]): T | null {
  return [...items].sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at))[0] ?? null;
}

export function isRunnableSession(session: SessionRecord): boolean {
  return !["cancelled", "completed", "failed"].includes(session.status);
}

export function buildWorkspaceTreeData(
  tasks: TaskRecord[],
  sessionsByTaskId: Record<string, SessionRecord[]>,
  workspaceByTaskId: Record<string, WorkspaceTree | undefined>,
): WorkspaceTreeNode[] {
  return tasks.map((task) => {
    const sessions = [...(sessionsByTaskId[task.id] ?? [])].sort(
      (a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at),
    );
    const files = workspaceByTaskId[task.id]?.files ?? [];
    const folderNodes = WORKSPACE_FOLDERS.map((folder) => ({
      id: `folder:${task.id}:${folder}`,
      name: `${folder}/`,
      kind: "folder" as const,
      taskId: task.id,
      path: folder,
      children: files
        .filter((file) => file.path === folder || file.path.startsWith(`${folder}/`))
        .map((file) => fileToTreeNode(task.id, file)),
    }));
    return {
      id: `task:${task.id}`,
      name: task.title ?? task.brief,
      kind: "task" as const,
      taskId: task.id,
      children: [...folderNodes],
    };
  });
}

function fileToTreeNode(taskId: string, file: WorkspaceFile): WorkspaceTreeNode {
  const name = file.path.split("/").at(-1) ?? file.path;
  return { id: `file:${taskId}:${file.path}`, name, kind: "file", taskId, path: file.path };
}
```

- [x] **Step 3: Verify build**

```bash
cd apps/web
npm run build
```

Expected: PASS.

- [x] **Step 4: Commit**

```bash
git add apps/web/src/shell/AppShell.tsx apps/web/src/shell/state/useWorkspaces.ts
git commit -m "feat: update AppShell to use Query hooks; remove interval polling and draftReloadToken"
```

---

### Task 7: Update `AppShell.test.tsx` to use TanStack Router test harness

**Files:**
- Modify: `apps/web/src/shell/__tests__/AppShell.test.tsx`

- [x] **Step 1: Run existing tests to see what breaks**

```bash
cd apps/web
npm run test:unit -- src/shell/__tests__/AppShell.test.tsx
```

Expected: multiple failures because tests use `MemoryRouter` from `react-router-dom` and `useSearchParams`, which no longer exist in the app.

- [x] **Step 2: Replace the test file's router imports and render helper**

At the top of `apps/web/src/shell/__tests__/AppShell.test.tsx`, replace:

```tsx
import { MemoryRouter, useLocation } from "react-router-dom";
```

with:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider, useRouterState } from "@tanstack/react-router";
import { createAppRouter } from "../../App";
```

Add a render helper function before the `describe` block:

```tsx
function renderAppShell(initialUrl = "/") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createAppRouter(createMemoryHistory({ initialEntries: [initialUrl] }));
  return {
    ...render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    ),
    router,
  };
}
```

Replace `LocationProbe` (used to observe URL changes) with a TanStack Router equivalent:

```tsx
function LocationSearch({ onChange }: { onChange: (search: string) => void }) {
  const state = useRouterState();
  const search = state.location.search;
  useEffect(() => onChange(search), [search, onChange]);
  return null;
}
```

Note: `LocationSearch` must be rendered inside a `RouterProvider`. Wrap it inside the `renderAppShell` helper or render it as a sibling route component in tests that need URL observation.

- [x] **Step 3: Replace all `render(<MemoryRouter ...><AppShell /></MemoryRouter>)` calls**

Find every occurrence of:
```tsx
render(<MemoryRouter ...><AppShell /></MemoryRouter>)
```

and replace with:
```tsx
renderAppShell("/?task=task-1&session=session-1")
```

(Use the appropriate initial URL for each test.)

- [x] **Step 4: Run tests**

```bash
cd apps/web
npm run test:unit -- src/shell/__tests__/AppShell.test.tsx
```

Expected: PASS. Fix any remaining import errors (e.g. `useLocation` references).

- [x] **Step 5: Run full unit test suite**

```bash
cd apps/web
npm run test:unit
```

Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add apps/web/src/shell/__tests__/AppShell.test.tsx
git commit -m "test: migrate AppShell tests to TanStack Router test harness"
```

---

### Task 8: Full verification

**Files:** No code changes expected.

- [x] **Step 1: Backend tests (unchanged)**

```bash
.local/dev/.venv/Scripts/python.exe -m pytest -q
```

Expected: PASS.

- [x] **Step 2: Frontend unit tests**

```bash
cd apps/web
npm run test:unit
```

Expected: PASS.

- [x] **Step 3: Frontend build**

```bash
cd apps/web
npm run build
```

Expected: PASS.

- [x] **Step 4: E2E smoke (if local servers available)**

```bash
cd apps/web
npm run test:e2e
```

Expected: PASS. Deep-link test (`workbench-shell.spec.ts`) must pass --confirm it loads `?task=` and `?session=` from URL.

- [x] **Step 5: Confirm react-router-dom is no longer imported in app code**

```bash
grep -r "react-router-dom" apps/web/src --include="*.tsx" --include="*.ts"
```

Expected: zero matches.

- [x] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: final cleanup and verification for state governance migration"
```

---

## Self-Review

**Spec coverage:**
- TanStack Router typed search params: Tasks 1-- [done]
- TanStack Query data hooks: Task 3 [done]
- useWorkspaces dissolved: Tasks 4, 6 [done]
- SSE invalidation (path-based): Task 5 [done]
- Exponential backoff reconnect + catchup: Task 5 [done]
- Remove interval polling: Task 6 [done]
- Remove draftReloadToken: Task 6 [done]
- Remove clear-before-load in useTimeline: Task 5 [done]
- created_at in TimelineEvent + real timestamps: Task 2 [done]
- Test harness migration: Task 7 [done]

**Placeholder scan:** None found. All steps contain actual code.

**Type consistency:** `useTimeline(sessionId, taskId)` signature used consistently in Tasks 5 and 6. `useActiveWorkspace()` return shape matches AppShell usage in Task 6. `buildWorkspaceTreeData` signature unchanged from original `useWorkspaces.ts`.
