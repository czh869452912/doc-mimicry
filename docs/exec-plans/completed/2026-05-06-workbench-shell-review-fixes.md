# Workbench Shell Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the review regressions in the workbench shell so restored workspaces, session switching, drafts, command palette actions, and workspace tree activation behave consistently.

**Architecture:** Keep the shell as a thin composition layer over existing hooks and panes. Move side-effect ownership to the hook/component closest to the state it owns: workspace initialization belongs in `useWorkspaces`, timeline hydration belongs in `useTimeline`, draft hydration belongs in `AppShell`, and command execution should reuse the existing slash-command path. Avoid adding a new global store or workflow engine.

**Tech Stack:** React 19, TypeScript, Vite, Vitest with jsdom, Testing Library, Playwright, existing REST `api` module.

---

## Files

- Modify: `apps/web/src/shell/state/useWorkspaces.ts`
  - Make initial workspace loading stable and one-shot.
  - Keep `refreshActiveWorkspace` usable from callers without making the initial effect depend on mutable active selection state.
- Modify: `apps/web/src/shell/state/useTimeline.ts`
  - Fetch/reset timeline when `sessionId` changes.
  - Ignore stale async responses when sessions switch quickly.
- Modify: `apps/web/src/shell/AppShell.tsx`
  - Hydrate draft whenever `activeTask.id` changes.
  - Add stale-response protection for draft loading.
  - Wire command palette commands to the existing conversation command execution path.
- Modify: `apps/web/src/shell/panes/ConversationPane.tsx`
  - Optionally expose an imperative command submit prop if `AppShell` needs to trigger slash commands through the same implementation.
  - Prefer extracting shared command execution into a small hook/function if that keeps `ConversationPane` focused.
- Modify: `apps/web/src/shell/panes/WorkspacePane.tsx`
  - Stop opening folder nodes as files.
- Create: `apps/web/src/shell/__tests__/useTimeline.test.tsx`
  - Cover session-id-driven timeline hydration and stale response handling.
- Modify: `apps/web/src/shell/__tests__/useWorkspaces.test.ts`
  - Add hook-level or helper-level coverage for stable initial load behavior if practical.
- Create or modify: `apps/web/src/shell/__tests__/AppShell.test.tsx`
  - Cover restored draft hydration, command palette execution, and folder activation behavior with mocked API calls.
- Modify: `apps/web/tests/workbench-shell.spec.ts`
  - Add a high-level regression smoke path if backend fixtures make it reliable; otherwise leave coverage at Vitest level.

---

## Task 1: Stabilize Workspace Initialization

**Files:**
- Modify: `apps/web/src/shell/state/useWorkspaces.ts`
- Modify: `apps/web/src/shell/__tests__/useWorkspaces.test.ts`

- [ ] **Step 1: Write a failing hook test for one-shot initialization**

Add Testing Library render-hook coverage. If the project lacks `renderHook`, use `render` with a tiny component that calls `useWorkspaces` and records states.

```ts
import { act, render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../api";
import { useWorkspaces } from "../state/useWorkspaces";

vi.mock("../../api", () => ({
  api: {
    listDocTypes: vi.fn(),
    listTasks: vi.fn(),
    listTaskSessions: vi.fn(),
    getWorkspace: vi.fn(),
  },
}));

function Harness({ onState }: { onState: (state: ReturnType<typeof useWorkspaces>) => void }) {
  const state = useWorkspaces();
  onState(state);
  return null;
}

describe("useWorkspaces initialization", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.clearAllMocks();
  });

  it("loads initial workspace once and does not rerun when active state is set", async () => {
    vi.mocked(api.listDocTypes).mockResolvedValue([{ id: "prd", title: "PRD", has_skill: true, resource_groups: {} }]);
    vi.mocked(api.listTasks).mockResolvedValue([
      {
        id: "task-1",
        doc_type_id: "prd",
        brief: "Write a PRD",
        workspace_root: "workspace/task-1",
        created_at: "2026-05-06T08:00:00Z",
        updated_at: "2026-05-06T09:00:00Z",
      },
    ]);
    vi.mocked(api.listTaskSessions).mockResolvedValue([
      {
        id: "session-1",
        task_id: "task-1",
        status: "draft_ready",
        created_at: "2026-05-06T08:00:00Z",
        updated_at: "2026-05-06T09:00:00Z",
      },
    ]);
    vi.mocked(api.getWorkspace).mockResolvedValue({ task_id: "task-1", root: "workspace/task-1", files: [] });

    let latest!: ReturnType<typeof useWorkspaces>;
    render(<Harness onState={(state) => (latest = state)} />);

    await waitFor(() => expect(latest.loading).toBe(false));

    expect(api.listTasks).toHaveBeenCalledTimes(1);
    expect(api.listTaskSessions).toHaveBeenCalledTimes(1);
    expect(api.getWorkspace).toHaveBeenCalledTimes(1);
    expect(latest.activeTask?.id).toBe("task-1");
    expect(latest.activeSession?.id).toBe("session-1");
  });
});
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
cd apps/web
npm run test:unit -- src/shell/__tests__/useWorkspaces.test.ts
```

Expected before the fix: the new test fails because initial loading repeats, or the test harness exposes the unstable dependency problem.

- [ ] **Step 3: Refactor `refreshActiveWorkspace` to accept explicit state safely**

Replace the default-argument closure dependency with explicit nullable arguments plus a small wrapper for current state.

```ts
const refreshWorkspaceForTask = useCallback(
  async (task: TaskRecord | null, sessionOverride: SessionRecord | null = null) => {
    if (!task) {
      setWorkspaceTree(null);
      setSessions([]);
      setActiveSession(null);
      window.localStorage.removeItem(LAST_TASK_KEY);
      window.localStorage.removeItem(LAST_SESSION_KEY);
      return;
    }

    const [nextSessions, nextWorkspace] = await Promise.all([
      api.listTaskSessions(task.id),
      api.getWorkspace(task.id),
    ]);
    const preferredSession =
      (sessionOverride && nextSessions.find((session) => session.id === sessionOverride.id)) ??
      latestByUpdatedAt(nextSessions);

    setSessions(nextSessions);
    setWorkspaceTree(nextWorkspace);
    setActiveSession(preferredSession);
    window.localStorage.setItem(LAST_TASK_KEY, task.id);
    if (preferredSession) {
      window.localStorage.setItem(LAST_SESSION_KEY, preferredSession.id);
    } else {
      window.localStorage.removeItem(LAST_SESSION_KEY);
    }
  },
  [],
);

const refreshActiveWorkspace = useCallback(async () => {
  await refreshWorkspaceForTask(activeTask, activeSession);
}, [activeSession, activeTask, refreshWorkspaceForTask]);
```

- [ ] **Step 4: Make initial load depend only on stable helpers**

Update `loadInitialState` to call `refreshWorkspaceForTask` and depend on that stable callback, not on `refreshActiveWorkspace`.

```ts
const loadInitialState = useCallback(async () => {
  setLoading(true);
  setError(null);
  try {
    const [nextDocTypes, nextTasks] = await Promise.all([api.listDocTypes(), api.listTasks()]);
    setDocTypes(nextDocTypes);
    setTasks(nextTasks);

    const rememberedTaskId = window.localStorage.getItem(LAST_TASK_KEY);
    const nextTask = nextTasks.find((task) => task.id === rememberedTaskId) ?? latestByUpdatedAt(nextTasks);
    if (nextTask) {
      setActiveTask(nextTask);
      const nextSessions = await api.listTaskSessions(nextTask.id);
      const rememberedSessionId = window.localStorage.getItem(LAST_SESSION_KEY);
      const nextSession =
        nextSessions.find((session) => session.id === rememberedSessionId) ?? latestByUpdatedAt(nextSessions);
      await refreshWorkspaceForTask(nextTask, nextSession);
    } else {
      setActiveTask(null);
      await refreshWorkspaceForTask(null);
    }
  } catch (caught) {
    setError(caught instanceof Error ? caught.message : "Could not load workspaces");
  } finally {
    setLoading(false);
  }
}, [refreshWorkspaceForTask]);
```

- [ ] **Step 5: Update selection/session callers**

Ensure these call the explicit helper.

```ts
const selectTask = useCallback(
  async (task: TaskRecord) => {
    setActiveTask(task);
    await refreshWorkspaceForTask(task, null);
  },
  [refreshWorkspaceForTask],
);

const ensureSession = useCallback(async () => {
  if (!activeTask) return null;
  if (activeSession && isRunnableSession(activeSession)) return activeSession;
  const session = await api.createSession(activeTask.id);
  await refreshWorkspaceForTask(activeTask, session);
  return session;
}, [activeSession, activeTask, refreshWorkspaceForTask]);
```

- [ ] **Step 6: Run unit test**

Run:

```powershell
cd apps/web
npm run test:unit -- src/shell/__tests__/useWorkspaces.test.ts
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add apps/web/src/shell/state/useWorkspaces.ts apps/web/src/shell/__tests__/useWorkspaces.test.ts
git commit -m "fix: stabilize workspace initialization"
```

---

## Task 2: Hydrate Timeline on Session Changes

**Files:**
- Modify: `apps/web/src/shell/state/useTimeline.ts`
- Create: `apps/web/src/shell/__tests__/useTimeline.test.tsx`

- [ ] **Step 1: Write failing tests for session-driven refresh and stale response handling**

```tsx
import { render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { api } from "../../api";
import { useTimeline } from "../state/useTimeline";

vi.mock("../../api", () => ({
  api: {
    getTimeline: vi.fn(),
  },
}));

function Harness({
  sessionId,
  onRender,
}: {
  sessionId: string | null;
  onRender: (state: ReturnType<typeof useTimeline>) => void;
}) {
  const state = useTimeline(sessionId);
  onRender(state);
  return null;
}

describe("useTimeline", () => {
  it("refreshes when session id changes", async () => {
    vi.mocked(api.getTimeline).mockResolvedValueOnce([
      { id: "event-1", actor: "agent", kind: "generate_outline", summary: "Outlined", paths: [], status: "succeeded" },
    ]);

    let latest!: ReturnType<typeof useTimeline>;
    render(<Harness sessionId="session-1" onRender={(state) => (latest = state)} />);

    await waitFor(() => expect(latest.events.map((event) => event.id)).toEqual(["event-1"]));
    expect(api.getTimeline).toHaveBeenCalledWith("session-1");
  });

  it("clears events when there is no session", async () => {
    let latest!: ReturnType<typeof useTimeline>;
    const { rerender } = render(<Harness sessionId="session-1" onRender={(state) => (latest = state)} />);
    vi.mocked(api.getTimeline).mockResolvedValueOnce([
      { id: "event-1", actor: "agent", kind: "generate_outline", summary: "Outlined", paths: [], status: "succeeded" },
    ]);

    rerender(<Harness sessionId={null} onRender={(state) => (latest = state)} />);

    await waitFor(() => expect(latest.events).toEqual([]));
  });
});
```

- [ ] **Step 2: Run the failing timeline tests**

Run:

```powershell
cd apps/web
npm run test:unit -- src/shell/__tests__/useTimeline.test.tsx
```

Expected before fix: first test fails because no automatic fetch occurs.

- [ ] **Step 3: Add session-id effect with stale response guard**

Modify `useTimeline.ts`.

```ts
import { useCallback, useEffect, useMemo, useState } from "react";

export function useTimeline(sessionId: string | null | undefined) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const refreshTimeline = useCallback(async () => {
    if (!sessionId) {
      setEvents([]);
      setError(null);
      return [];
    }
    setLoading(true);
    setError(null);
    try {
      const nextEvents = replaceWithIdDedup(await api.getTimeline(sessionId));
      setEvents(nextEvents);
      return nextEvents;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not refresh timeline");
      return [];
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    let cancelled = false;

    async function loadForSession() {
      if (!sessionId) {
        setEvents([]);
        setError(null);
        setLoading(false);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const nextEvents = replaceWithIdDedup(await api.getTimeline(sessionId));
        if (!cancelled) setEvents(nextEvents);
      } catch (caught) {
        if (!cancelled) setError(caught instanceof Error ? caught.message : "Could not refresh timeline");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadForSession();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const resetTimeline = useCallback(() => {
    setEvents([]);
    setError(null);
  }, []);

  const presentations = useMemo(() => events.map(timelinePresentation), [events]);

  return { error, events, loading, presentations, refreshTimeline, resetTimeline };
}
```

- [ ] **Step 4: Run timeline tests**

Run:

```powershell
cd apps/web
npm run test:unit -- src/shell/__tests__/useTimeline.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/web/src/shell/state/useTimeline.ts apps/web/src/shell/__tests__/useTimeline.test.tsx
git commit -m "fix: hydrate timeline on session changes"
```

---

## Task 3: Hydrate Draft on Active Task Changes

**Files:**
- Modify: `apps/web/src/shell/AppShell.tsx`
- Create or modify: `apps/web/src/shell/__tests__/AppShell.test.tsx`

- [ ] **Step 1: Write a failing AppShell test for restored draft hydration**

Mock `useWorkspaces` or the API. Prefer API-level mock if existing shell integration tests already mount real hooks.

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { api } from "../../api";
import { AppShell } from "../AppShell";

vi.mock("../../api", () => ({
  api: {
    listDocTypes: vi.fn(),
    listTasks: vi.fn(),
    listTaskSessions: vi.fn(),
    getWorkspace: vi.fn(),
    getTimeline: vi.fn(),
    getDraft: vi.fn(),
    updateDraft: vi.fn(),
  },
}));

describe("AppShell draft hydration", () => {
  it("loads the active task draft after restored workspace state is available", async () => {
    vi.mocked(api.listDocTypes).mockResolvedValue([{ id: "prd", title: "PRD", has_skill: true, resource_groups: {} }]);
    vi.mocked(api.listTasks).mockResolvedValue([
      {
        id: "task-1",
        doc_type_id: "prd",
        brief: "Write a PRD",
        workspace_root: "workspace/task-1",
        created_at: "2026-05-06T08:00:00Z",
        updated_at: "2026-05-06T09:00:00Z",
      },
    ]);
    vi.mocked(api.listTaskSessions).mockResolvedValue([]);
    vi.mocked(api.getWorkspace).mockResolvedValue({ task_id: "task-1", root: "workspace/task-1", files: [] });
    vi.mocked(api.getTimeline).mockResolvedValue([]);
    vi.mocked(api.getDraft).mockResolvedValue({ markdown: "# Restored draft" });
    vi.mocked(api.updateDraft).mockResolvedValue({ markdown: "# Restored draft" });

    render(<AppShell />);

    await waitFor(() => expect(api.getDraft).toHaveBeenCalledWith("task-1"));
    expect(await screen.findByDisplayValue("# Restored draft")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the failing AppShell test**

Run:

```powershell
cd apps/web
npm run test:unit -- src/shell/__tests__/AppShell.test.tsx
```

Expected before fix: draft textarea/editor remains empty or `getDraft` is not called for the restored task.

- [ ] **Step 3: Add task-id-driven draft loading with cancellation**

In `AppShell.tsx`, add an effect after `timeline` creation.

```tsx
useEffect(() => {
  let cancelled = false;
  const taskId = workspaces.activeTask?.id;

  if (!taskId) {
    setDraft("");
    return;
  }

  async function loadActiveDraft() {
    try {
      const response = await api.getDraft(taskId);
      if (!cancelled) setDraft(response.markdown);
    } catch {
      if (!cancelled) setDraft("");
    }
  }

  void loadActiveDraft();
  return () => {
    cancelled = true;
  };
}, [workspaces.activeTask?.id]);
```

- [ ] **Step 4: Remove duplicate create-only draft loading**

In `onCreateWorkspace`, rely on the active-task effect instead of manually calling `loadDraft`.

```tsx
onCreateWorkspace={async (docTypeId, brief) => {
  await workspaces.createWorkspace(docTypeId, brief);
}}
```

Keep `loadDraft` only if conversation refresh needs an immediate reload after backend actions. If retained, make it accept a task id and reuse the same stale-protected helper pattern.

- [ ] **Step 5: Run AppShell test**

Run:

```powershell
cd apps/web
npm run test:unit -- src/shell/__tests__/AppShell.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/web/src/shell/AppShell.tsx apps/web/src/shell/__tests__/AppShell.test.tsx
git commit -m "fix: hydrate draft for active workspace"
```

---

## Task 4: Wire Command Palette to Slash Command Execution

**Files:**
- Modify: `apps/web/src/shell/AppShell.tsx`
- Modify: `apps/web/src/shell/panes/ConversationPane.tsx`
- Modify: `apps/web/src/shell/__tests__/AppShell.test.tsx`

- [ ] **Step 1: Extract reusable command execution**

Create a helper inside `AppShell.tsx` that can be called by the palette and by `ConversationPane`, or move the execution function from `ConversationPane` into a small shared hook if the component starts to grow.

Preferred minimal implementation: add an optional `queuedComposerCommand` prop to `ConversationPane`.

```tsx
const [queuedCommand, setQueuedCommand] = useState<string | null>(null);

<ConversationPane
  queuedCommand={queuedCommand}
  onQueuedCommandHandled={() => setQueuedCommand(null)}
  ...
/>

<CommandPalette
  open={commandOpen}
  onClose={() => setCommandOpen(false)}
  onRunCommand={(command) => setQueuedCommand(command)}
/>
```

- [ ] **Step 2: Update `ConversationPane` props**

```tsx
interface ConversationPaneProps {
  activeSession: SessionRecord | null;
  activeTask: TaskRecord | null;
  ensureSession: () => Promise<SessionRecord | null>;
  error: string | null;
  loading: boolean;
  onOpenPath: (path: string) => Promise<void>;
  onQueuedCommandHandled?: () => void;
  presentations: Presentation[];
  queuedCommand?: string | null;
  refreshTimeline: () => Promise<unknown>;
  refreshWorkspace: () => Promise<unknown>;
}
```

- [ ] **Step 3: Refactor submit logic to accept explicit input**

```tsx
async function submitInput(rawInput: string) {
  const input = rawInput.trimEnd();
  if (!input) return;
  setStatus("Working...");

  try {
    const commandResult = await executeSlashCommand(input, {
      activeTask,
      ensureSession,
      openArtifact: onOpenPath,
      openHelp: () => setShowHelp(true),
      refreshTimeline,
      refreshWorkspace,
    });
    if (!commandResult.handled) {
      const session = await ensureSession();
      if (!session) {
        setStatus("Create a workspace first.");
        return;
      }
      await api.sendMessage(session.id, input);
      await refreshWorkspace();
      await refreshTimeline();
    }
    setStatus(commandResult.message ?? "Message processed.");
  } catch (caught) {
    setStatus(caught instanceof Error ? caught.message : "Conversation action failed.");
  }
}

async function submitComposer() {
  const input = composer;
  setComposer("");
  await submitInput(input);
}
```

- [ ] **Step 4: Consume queued palette commands**

```tsx
useEffect(() => {
  if (!queuedCommand) return;
  void submitInput(queuedCommand).finally(() => {
    onQueuedCommandHandled?.();
  });
}, [queuedCommand]);
```

Make sure `ConversationPane.tsx` imports `useEffect`.

- [ ] **Step 5: Write a failing/passing test for palette `/help`**

In `AppShell.test.tsx`:

```tsx
it("runs slash commands selected from the command palette", async () => {
  // reuse the same mocked initial workspace setup from the draft hydration test
  render(<AppShell />);

  await screen.findByText("Write a PRD");
  await userEvent.keyboard("{Control>}k{/Control}");
  await screen.findByRole("option", { name: /\/help/i }).click();

  expect(await screen.findByText("Slash commands")).toBeInTheDocument();
});
```

- [ ] **Step 6: Run AppShell tests**

Run:

```powershell
cd apps/web
npm run test:unit -- src/shell/__tests__/AppShell.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add apps/web/src/shell/AppShell.tsx apps/web/src/shell/panes/ConversationPane.tsx apps/web/src/shell/__tests__/AppShell.test.tsx
git commit -m "fix: run command palette actions"
```

---

## Task 5: Prevent Folder Nodes from Opening as Files

**Files:**
- Modify: `apps/web/src/shell/panes/WorkspacePane.tsx`
- Modify: `apps/web/src/shell/__tests__/AppShell.test.tsx` or create `apps/web/src/shell/__tests__/WorkspacePane.test.tsx`

- [ ] **Step 1: Write a failing pane test**

Prefer a focused `WorkspacePane` test.

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { WorkspacePane } from "../panes/WorkspacePane";

describe("WorkspacePane activation", () => {
  it("does not open folder nodes as files", async () => {
    const onOpenFile = vi.fn();

    render(
      <WorkspacePane
        activeSession={null}
        activeTask={null}
        docTypes={[]}
        error={null}
        loading={false}
        nodes={[
          {
            id: "task:task-1",
            name: "Task",
            kind: "task",
            taskId: "task-1",
            children: [{ id: "folder:task-1:draft", name: "draft/", kind: "folder", taskId: "task-1", path: "draft" }],
          },
        ]}
        onCreateWorkspace={vi.fn()}
        onOpenFile={onOpenFile}
        onSelectSession={vi.fn()}
        onSelectTask={vi.fn()}
      />,
    );

    await userEvent.click(screen.getByText("draft/"));

    expect(onOpenFile).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run the failing pane test**

Run:

```powershell
cd apps/web
npm run test:unit -- src/shell/__tests__/WorkspacePane.test.tsx
```

Expected before fix: `onOpenFile` is called with `"draft"`.

- [ ] **Step 3: Change activation behavior**

```tsx
onActivate={(node) => {
  const data = node.data;
  if (data.kind === "task" && data.taskId) onSelectTask(data.taskId);
  if (data.kind === "session" && data.sessionId) onSelectSession(data.sessionId);
  if (data.kind === "folder") node.toggle();
  if (data.kind === "file" && data.path) onOpenFile(data.path);
}}
```

If `react-arborist`'s `node.toggle()` is unavailable in the type surface, use the documented open/close API exposed on the node renderer or simply no-op folder activation and rely on the chevron/tree default behavior.

- [ ] **Step 4: Run pane test**

Run:

```powershell
cd apps/web
npm run test:unit -- src/shell/__tests__/WorkspacePane.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/web/src/shell/panes/WorkspacePane.tsx apps/web/src/shell/__tests__/WorkspacePane.test.tsx
git commit -m "fix: keep workspace folders from opening as files"
```

---

## Final Verification

- [ ] **Step 1: Run focused shell unit tests**

```powershell
cd apps/web
npm run test:unit -- src/shell/__tests__/useWorkspaces.test.ts src/shell/__tests__/useTimeline.test.tsx src/shell/__tests__/AppShell.test.tsx src/shell/__tests__/WorkspacePane.test.tsx
```

Expected: all tests PASS.

- [ ] **Step 2: Run full web unit suite**

```powershell
cd apps/web
npm run test:unit
```

Expected: all tests PASS.

- [ ] **Step 3: Run web build**

```powershell
cd apps/web
npm run build
```

Expected: TypeScript passes and Vite build completes. Existing chunk-size warnings are acceptable if unchanged.

- [ ] **Step 4: Run web e2e smoke tests**

```powershell
cd apps/web
npm run test:e2e
```

Expected: all Playwright tests PASS.

- [ ] **Step 5: Run backend/contracts regression suite**

```powershell
python -m pytest packages/contracts/tests packages/workspace/tests packages/timeline/tests tools/import/tests services/api/tests agent/runtime-adapters/mock/tests tests -q
```

Expected: all tests PASS.

- [ ] **Step 6: Documentation-only structure check if plan/spec docs changed**

```powershell
Get-ChildItem -Recurse -File | Select-Object FullName
```

Expected: command completes and shows repo files.

---

## Self-Review Checklist

- [ ] Finding 1 covered by Task 1: initial loader no longer depends on mutable active selection state.
- [ ] Finding 2 covered by Task 2: timeline loads and resets on `sessionId` changes.
- [ ] Finding 3 covered by Task 3: draft loads on `activeTask.id` changes with stale response protection.
- [ ] Finding 4 covered by Task 4: command palette runs slash commands instead of no-op.
- [ ] Additional review issue covered by Task 5: folder nodes are not sent to the file-content API.
- [ ] No new fixed workflow/DAG behavior is introduced.
- [ ] Markdown remains the internal document format.
- [ ] Management and authoring surfaces remain separated.
