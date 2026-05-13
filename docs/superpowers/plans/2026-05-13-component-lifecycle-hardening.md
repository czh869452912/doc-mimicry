# Component Lifecycle Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the confirmed plugin/component lifecycle issues from `docs/reviews/active/2026-05-13-plugin-component-lifecycle-audit.md` and add guardrails that make future integrations check runtime callbacks, scoped async state, a11y semantics, query placeholder behavior, and persisted layout data.

**Architecture:** Keep fixes local to the React workbench surface. Add small helper functions where they make component contracts testable, then wire the UI to those helpers. Capture recurrence prevention in focused tests plus a short quality checklist linked from `AGENTS.md`.

**Tech Stack:** React 19, TypeScript, Vitest, Testing Library, TanStack Query, assistant-ui external store runtime, Radix Tabs/Dialog, cmdk, react-resizable-panels, react-arborist, CodeMirror, zod, react-hook-form.

---

## Scope

- Primary audit source: `docs/reviews/active/2026-05-13-plugin-component-lifecycle-audit.md`.
- Fix first: ISSUE-01, ISSUE-09, ISSUE-02, ISSUE-12, ISSUE-15, ISSUE-11, ISSUE-14, ISSUE-18, ISSUE-16, ISSUE-19, ISSUE-21.
- Add guardrails for remaining confirmed low-risk issues: ISSUE-03, ISSUE-04, ISSUE-06, ISSUE-07, ISSUE-08, ISSUE-10, ISSUE-13, ISSUE-17, ISSUE-20.
- Preserve the product direction from `AGENTS.md`: interactive document workbench, Markdown as internal format, management and authoring as separate UI surfaces.

## Non-Goals

- Do not redesign the workbench layout.
- Do not change backend session semantics unless a frontend test proves the API contract cannot support cancellation or refresh.
- Do not replace assistant-ui, Radix, TanStack Query, CodeMirror, react-arborist, or react-resizable-panels.
- Do not convert this into a fixed workflow engine.

## Files And Responsibilities

- Modify `apps/web/src/shell/assistant/useDocAgentAssistantRuntime.ts`: assistant-ui adapter callbacks, task-scoped attachment references, runtime capability wrapper.
- Create `apps/web/src/shell/assistant/__tests__/useDocAgentAssistantRuntime.test.tsx`: runtime adapter contract tests using a mocked `useExternalStoreRuntime`.
- Modify `apps/web/src/shell/panes/ConversationPane.tsx`: single idempotent cancellation path and runtime cancellation wiring.
- Modify `apps/web/src/shell/panes/__tests__/ConversationPane.test.tsx`: cancellation, reload, and refresh assertions.
- Modify `apps/web/src/shell/panes/EditorPane.tsx`: remove nested interactive tab close button.
- Create `apps/web/src/shell/panes/__tests__/EditorPane.test.tsx`: tab close a11y and tab activation behavior.
- Modify `apps/web/src/shell/theme/shell.css`: tab wrapper and close button spacing after markup changes.
- Modify `apps/web/src/shell/CommandPalette.tsx`: keyboard and focus-safe dismissal.
- Create `apps/web/src/shell/__tests__/CommandPalette.test.tsx`: Escape, overlay click, and item selection behavior.
- Modify `apps/web/src/shell/editor/DraftEditor.tsx`: memoize CodeMirror extensions and selection listener.
- Create `apps/web/src/shell/editor/__tests__/DraftEditor.test.tsx`: stable extension identity and selection callback behavior.
- Modify `apps/web/src/shell/conversation/cards/OutlineCard.tsx`: keep dirty outline edits from being overwritten by late fetches.
- Create `apps/web/src/shell/conversation/cards/__tests__/OutlineCard.test.tsx`: dirty edit protection and approve payload.
- Modify `apps/web/src/shell/state/useDraft.ts`: remove cross-task placeholder data.
- Modify `apps/web/src/shell/state/useWorkspaceTree.ts`: remove cross-task placeholder data.
- Modify `apps/web/src/shell/__tests__/AppShell.test.tsx`: stale draft/workspace display assertions.
- Modify `apps/web/src/shell/state/useCollapse.ts`: sanitize panel sizes before using or storing them.
- Modify `apps/web/src/shell/__tests__/useCollapse.test.ts`: panel size normalization coverage.
- Modify `apps/web/src/shell/panes/WorkspacePane.tsx`: require non-empty title and render title errors.
- Modify `apps/web/src/shell/panes/__tests__/WorkspacePane.test.tsx`: title validation coverage.
- Verify `apps/web/src/shell/AppShell.tsx`: workspace creation still passes `{ title, description }` through unchanged.
- Verify `apps/web/src/shell/state/useActiveWorkspace.ts`: `createWorkspace` and mutation input still accept `{ title, description }`.
- Modify `apps/web/src/shell/assistant/docAgentAssistantMessages.ts`: preserve unknown statuses as safe incomplete/error states.
- Modify `apps/web/src/shell/assistant/__tests__/docAgentAssistantMessages.test.ts`: unknown status regression.
- Modify `docs/quality/testing.md`: add frontend component integration test expectations.
- Create `docs/quality/frontend-component-integration-checklist.md`: recurring checklist for third-party component integration.
- Modify `AGENTS.md`: add one short pointer to the frontend integration checklist for `apps/web` changes.

## Task 1: Assistant Runtime Cancellation And Scoped Attachments

**Files:**
- Modify: `apps/web/src/shell/assistant/useDocAgentAssistantRuntime.ts`
- Modify: `apps/web/src/shell/panes/ConversationPane.tsx`
- Create: `apps/web/src/shell/assistant/__tests__/useDocAgentAssistantRuntime.test.tsx`
- Modify: `apps/web/src/shell/panes/__tests__/ConversationPane.test.tsx`

- [ ] **Step 1: Write failing runtime adapter tests**

Create `apps/web/src/shell/assistant/__tests__/useDocAgentAssistantRuntime.test.tsx` with this shape:

```tsx
import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AppendMessage } from "@assistant-ui/react";
import {
  addImportedAttachmentForTask,
  takeImportedAttachmentsForTask,
  useDocAgentAssistantRuntime,
} from "../useDocAgentAssistantRuntime";
import type { MessageAttachment } from "../../../types";

const { capturedRuntimeOptions } = vi.hoisted(() => ({
  capturedRuntimeOptions: [] as unknown[],
}));

vi.mock("@assistant-ui/react", async () => {
  const actual = await vi.importActual<typeof import("@assistant-ui/react")>("@assistant-ui/react");
  return {
    ...actual,
    useExternalStoreRuntime: vi.fn((options: unknown) => {
      capturedRuntimeOptions.push(options);
      return { __runtime: true };
    }),
  };
});

function Harness(props: Partial<Parameters<typeof useDocAgentAssistantRuntime>[0]>) {
  useDocAgentAssistantRuntime({
    activeTaskId: "task-1",
    events: [],
    isRunning: true,
    onCancel: vi.fn(),
    onReloadInput: vi.fn(),
    onSubmitInput: vi.fn(),
    ...props,
  });
  return null;
}

function latestOptions() {
  return capturedRuntimeOptions.at(-1) as {
    onCancel?: () => Promise<void>;
    onNew: (message: AppendMessage) => Promise<void>;
  };
}

describe("useDocAgentAssistantRuntime", () => {
  beforeEach(() => {
    capturedRuntimeOptions.length = 0;
    vi.clearAllMocks();
  });

  it("wires assistant-ui runtime cancellation to the caller", async () => {
    const onCancel = vi.fn().mockResolvedValue(undefined);

    render(<Harness onCancel={onCancel} />);

    await latestOptions().onCancel?.();

    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("takes attachments only for the requested task", () => {
    const taskOneAttachment: MessageAttachment = {
      name: "task-1.md",
      markdown_path: "inputs/task-1.md",
    };
    const taskTwoAttachment: MessageAttachment = {
      name: "task-2.md",
      markdown_path: "inputs/task-2.md",
    };
    const store = addImportedAttachmentForTask(
      addImportedAttachmentForTask({}, "task-1", taskOneAttachment),
      "task-2",
      taskTwoAttachment,
    );

    const result = takeImportedAttachmentsForTask(store, "task-2");

    expect(result.attachments).toEqual([taskTwoAttachment]);
    expect(result.nextStore).toEqual({ "task-1": [taskOneAttachment] });
  });
});
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
cd apps/web
npm run test:unit -- src/shell/assistant/__tests__/useDocAgentAssistantRuntime.test.tsx src/shell/panes/__tests__/ConversationPane.test.tsx
```

Expected: FAIL because `onCancel` is missing and attachment references are stored in one cross-task array.

- [ ] **Step 3: Implement task-scoped attachment storage and runtime cancellation**

In `apps/web/src/shell/assistant/useDocAgentAssistantRuntime.ts`, change the options interface and internal ref shape:

```ts
interface UseDocAgentAssistantRuntimeOptions {
  activeTaskId: string | null;
  events: TimelineEvent[];
  isRunning: boolean;
  onCancel?: () => Promise<void>;
  onReloadInput?: (parentMessageId: string | null) => Promise<void>;
  onSubmitInput: (input: string, attachments?: MessageAttachment[]) => Promise<void>;
}

type ImportedAttachmentStore = Record<string, MessageAttachment[]>;

export function addImportedAttachmentForTask(
  store: ImportedAttachmentStore,
  taskId: string | null,
  reference: MessageAttachment,
) {
  if (!taskId) return store;
  return {
    ...store,
    [taskId]: [...(store[taskId] ?? []), reference],
  };
}

export function takeImportedAttachmentsForTask(
  store: ImportedAttachmentStore,
  taskId: string | null,
) {
  if (!taskId) return { nextStore: store, attachments: [] as MessageAttachment[] };
  const { [taskId]: attachments = [], ...rest } = store;
  return { nextStore: rest, attachments };
}
```

Then wire those helpers inside the hook:

```ts
const importedAttachmentReferencesRef = useRef<ImportedAttachmentStore>({});

const attachmentAdapter = useMemo(
  () =>
    createDocAgentTextAttachmentAdapter({
      taskId: activeTaskId,
      onImported: (reference) => {
        importedAttachmentReferencesRef.current = addImportedAttachmentForTask(
          importedAttachmentReferencesRef.current,
          activeTaskId,
          reference,
        );
      },
    }),
  [activeTaskId],
);

return useExternalStoreRuntime<ThreadMessage>({
  adapters: {
    attachments: attachmentAdapter,
  },
  isRunning,
  messages,
  onCancel,
  onNew: async (message: AppendMessage) => {
    const result = takeImportedAttachmentsForTask(importedAttachmentReferencesRef.current, activeTaskId);
    importedAttachmentReferencesRef.current = result.nextStore;
    await onSubmitInput(textFromAppendMessage(message), result.attachments);
  },
  onReload: async (parentId: string | null) => {
    await onReloadInput?.(parentId);
  },
  unstable_capabilities: { copy: true },
});
```

- [ ] **Step 4: Consolidate cancellation in `ConversationPane`**

In `apps/web/src/shell/panes/ConversationPane.tsx`, make `cancelActiveSession` idempotent and pass it to the runtime:

```ts
const cancellationInFlightRef = useRef(false);

const cancelActiveSession = useCallback(async () => {
  if (!activeSession || cancellationInFlightRef.current) return;
  cancellationInFlightRef.current = true;
  try {
    await api.cancelSession(activeSession.id);
    await refreshTimeline();
    await refreshSessions?.();
    setStatus("Cancelled.");
  } catch (caught) {
    setStatus(caught instanceof Error ? caught.message : "Cancel failed.");
  } finally {
    cancellationInFlightRef.current = false;
  }
}, [activeSession, refreshTimeline, refreshSessions]);
```

Update the running branch in `submitOrCancel`:

```ts
if (isRunning && activeSession) {
  if (input) {
    setStatus("Agent is working.");
    return;
  }
  await cancelActiveSession();
  return;
}
```

Pass `onCancel`:

```tsx
const runtime = useDocAgentAssistantRuntime({
  activeTaskId: activeTask?.id ?? null,
  events,
  isRunning,
  onCancel: cancelActiveSession,
  onReloadInput: reloadInput,
  onSubmitInput: submitOrCancel,
});
```

- [ ] **Step 5: Run focused tests**

Run:

```powershell
cd apps/web
npm run test:unit -- src/shell/assistant/__tests__/useDocAgentAssistantRuntime.test.tsx src/shell/panes/__tests__/ConversationPane.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/web/src/shell/assistant/useDocAgentAssistantRuntime.ts apps/web/src/shell/assistant/__tests__/useDocAgentAssistantRuntime.test.tsx apps/web/src/shell/panes/ConversationPane.tsx apps/web/src/shell/panes/__tests__/ConversationPane.test.tsx
git commit -m "fix: wire assistant runtime cancellation"
```

## Task 2: Tab Semantics And Command Palette Dismissal

**Files:**
- Modify: `apps/web/src/shell/panes/EditorPane.tsx`
- Modify: `apps/web/src/shell/theme/shell.css`
- Create: `apps/web/src/shell/panes/__tests__/EditorPane.test.tsx`
- Modify: `apps/web/src/shell/CommandPalette.tsx`
- Create: `apps/web/src/shell/__tests__/CommandPalette.test.tsx`

- [ ] **Step 1: Write failing editor tab tests**

Create `apps/web/src/shell/panes/__tests__/EditorPane.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { EditorPane } from "../EditorPane";
import type { EditorTab } from "../../editor/useTabs";

const tabs: EditorTab[] = [
  { id: "draft", title: "Draft", kind: "draft" },
  { id: "file:notes.md", title: "notes.md", kind: "file", path: "notes.md", content: "Notes" },
];

function renderEditor(overrides: Partial<Parameters<typeof EditorPane>[0]> = {}) {
  return render(
    <EditorPane
      activeSessionId={null}
      activeTabId="draft"
      draft="Current draft"
      tabs={tabs}
      taskId="task-1"
      onCloseTab={vi.fn()}
      onDraftChange={vi.fn()}
      onTabChange={vi.fn()}
      {...overrides}
    />,
  );
}

describe("EditorPane tabs", () => {
  it("keeps tab triggers free of nested buttons", () => {
    renderEditor();

    const tabButtons = screen.getAllByRole("tab");

    for (const tabButton of tabButtons) {
      expect(tabButton.querySelector("button")).toBeNull();
    }
  });

  it("closes a file tab from a separate close control", async () => {
    const user = userEvent.setup();
    const onCloseTab = vi.fn();
    renderEditor({ onCloseTab });

    await user.click(screen.getByRole("button", { name: "Close notes.md" }));

    expect(onCloseTab).toHaveBeenCalledWith("file:notes.md");
  });
});
```

- [ ] **Step 2: Change the tab markup**

In `apps/web/src/shell/panes/EditorPane.tsx`, render each tab as a wrapper with a Radix trigger plus a sibling close button:

```tsx
{tabs.map((tab) => (
  <span className="editor-tab-item" key={tab.id}>
    <TabsTrigger className="editor-tab-trigger" value={tab.id}>
      <span>{tab.id === "draft" ? "Pinned " : ""}</span>
      <span>{tab.title}</span>
    </TabsTrigger>
    {tab.id !== "draft" && (
      <button
        className="tab-close"
        type="button"
        aria-label={`Close ${tab.title}`}
        onClick={() => onCloseTab(tab.id)}
      >
        <X size={12} aria-hidden="true" />
      </button>
    )}
  </span>
))}
```

If the CSS currently depends on `.editor-tab-trigger .tab-close`, move spacing to `.editor-tab-item` in the stylesheet that defines editor tab classes.

In `apps/web/src/shell/theme/shell.css`, add or adjust:

```css
.editor-tab-item {
  align-items: center;
  display: inline-flex;
  gap: 0.25rem;
}

.editor-tab-item .tab-close {
  flex: 0 0 auto;
}
```

- [ ] **Step 3: Write failing command palette tests**

Create `apps/web/src/shell/__tests__/CommandPalette.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { CommandPalette } from "../CommandPalette";

describe("CommandPalette", () => {
  it("closes when Escape is pressed", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<CommandPalette open onClose={onClose} onRunCommand={vi.fn()} />);

    await user.keyboard("{Escape}");

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("does not close when typing inside the command input", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<CommandPalette open onClose={onClose} onRunCommand={vi.fn()} />);

    await user.type(screen.getByPlaceholderText("Run command..."), "start");

    expect(onClose).not.toHaveBeenCalled();
  });

  it("runs and closes the selected command", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const onRunCommand = vi.fn();
    render(<CommandPalette open onClose={onClose} onRunCommand={onRunCommand} />);

    await user.click(screen.getByText("/start"));

    expect(onRunCommand).toHaveBeenCalledWith("/start");
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 4: Implement keyboard dismissal**

In `apps/web/src/shell/CommandPalette.tsx`, add an Escape handler on the overlay:

```tsx
<div
  className="command-overlay"
  role="presentation"
  onKeyDown={(event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
    }
  }}
  onMouseDown={onClose}
>
```

Keep the existing `onMouseDown={(event) => event.stopPropagation()}` on the menu so inside clicks do not dismiss unless the item selection explicitly calls `onClose`.

- [ ] **Step 5: Run focused tests**

Run:

```powershell
cd apps/web
npm run test:unit -- src/shell/panes/__tests__/EditorPane.test.tsx src/shell/__tests__/CommandPalette.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/web/src/shell/panes/EditorPane.tsx apps/web/src/shell/theme/shell.css apps/web/src/shell/panes/__tests__/EditorPane.test.tsx apps/web/src/shell/CommandPalette.tsx apps/web/src/shell/__tests__/CommandPalette.test.tsx
git commit -m "fix: correct tab and command palette interactions"
```

## Task 3: Draft Editor Stability And Outline Dirty Edit Protection

**Files:**
- Modify: `apps/web/src/shell/editor/DraftEditor.tsx`
- Create: `apps/web/src/shell/editor/__tests__/DraftEditor.test.tsx`
- Modify: `apps/web/src/shell/conversation/cards/OutlineCard.tsx`
- Create: `apps/web/src/shell/conversation/cards/__tests__/OutlineCard.test.tsx`

- [ ] **Step 1: Memoize CodeMirror extensions**

In `apps/web/src/shell/editor/DraftEditor.tsx`, import React memo hooks and keep extensions stable unless `onSelection` changes:

```ts
import { useMemo } from "react";
```

Replace the inline listener and extension array with:

```ts
const selectionListener = useMemo(
  () =>
    EditorView.updateListener.of((viewUpdate) => {
      if (!viewUpdate.selectionSet) return;
      const selection = viewUpdate.state.sliceDoc(
        viewUpdate.state.selection.main.from,
        viewUpdate.state.selection.main.to,
      );
      onSelection?.(selection);
    }),
  [onSelection],
);

const extensions = useMemo(
  () => [markdown(), EditorView.lineWrapping, selectionListener],
  [selectionListener],
);
```

Then pass `extensions={extensions}`.

- [ ] **Step 2: Write DraftEditor extension stability tests**

Create `apps/web/src/shell/editor/__tests__/DraftEditor.test.tsx`:

```tsx
import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DraftEditor } from "../DraftEditor";

interface MockCodeMirrorProps {
  editable?: boolean;
  extensions: unknown[];
  onChange: (
    value: string,
    viewUpdate: {
      state: {
        selection: { main: { from: number; to: number } };
        sliceDoc: (from: number, to: number) => string;
      };
    },
  ) => void;
  value: string;
}

const { codeMirrorProps } = vi.hoisted(() => ({
  codeMirrorProps: [] as unknown[],
}));

function latestCodeMirrorProps() {
  return codeMirrorProps.at(-1) as MockCodeMirrorProps | undefined;
}

vi.mock("@uiw/react-codemirror", () => ({
  default: vi.fn((props: MockCodeMirrorProps) => {
    codeMirrorProps.push(props);
    return <textarea data-testid="mock-codemirror" readOnly={props.editable === false} value={props.value} />;
  }),
}));

function fakeViewUpdate(selectedText: string) {
  return {
    state: {
      selection: { main: { from: 0, to: selectedText.length } },
      sliceDoc: vi.fn(() => selectedText),
    },
  };
}

describe("DraftEditor", () => {
  beforeEach(() => {
    codeMirrorProps.length = 0;
    vi.clearAllMocks();
  });

  it("does not create a new extensions array when props are stable", () => {
    const onChange = vi.fn();
    const onSelection = vi.fn();
    const { rerender } = render(
      <DraftEditor markdown="First draft" onChange={onChange} onSelection={onSelection} />,
    );
    const firstExtensions = latestCodeMirrorProps()?.extensions;

    rerender(<DraftEditor markdown="Second draft" onChange={onChange} onSelection={onSelection} />);

    expect(latestCodeMirrorProps()?.extensions).toBe(firstExtensions);
  });

  it("forwards editor changes and current selected text", () => {
    const onChange = vi.fn();
    const onSelection = vi.fn();
    render(<DraftEditor markdown="First draft" onChange={onChange} onSelection={onSelection} />);

    latestCodeMirrorProps()?.onChange("Updated draft", fakeViewUpdate("selected passage"));

    expect(onChange).toHaveBeenCalledWith("Updated draft");
    expect(onSelection).toHaveBeenCalledWith("selected passage");
  });
});
```

Before the memoization change, the first test fails because `extensions={[markdown(), EditorView.lineWrapping, selectionListener]}` creates a new array on every render. After Step 1 is implemented, it passes and protects the CodeMirror integration from future regressions.

- [ ] **Step 3: Write outline dirty edit tests**

Create `apps/web/src/shell/conversation/cards/__tests__/OutlineCard.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../../../api";
import { OutlineCard } from "../OutlineCard";
import type { TimelineEvent } from "../../../../types";

vi.mock("../../../../api", () => ({
  api: {
    approveOutline: vi.fn(),
    getWorkspaceFile: vi.fn(),
  },
}));

const event: TimelineEvent = {
  actor: "agent",
  id: "evt-outline",
  kind: "propose_outline",
  paths: ["draft/outline.md"],
  raw_event_id: null,
  session_id: "session-1",
  status: "succeeded",
  summary: "Initial summary",
  task_id: "task-1",
};

describe("OutlineCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does not overwrite local outline edits when the file fetch resolves late", async () => {
    const user = userEvent.setup();
    let resolveFile!: (value: { content: string }) => void;
    vi.mocked(api.getWorkspaceFile).mockReturnValue(
      new Promise((resolve) => {
        resolveFile = resolve;
      }) as ReturnType<typeof api.getWorkspaceFile>,
    );

    render(
      <OutlineCard
        event={event}
        sessionId="session-1"
        taskId="task-1"
        onApproved={vi.fn()}
        onOpenPath={vi.fn()}
      />,
    );

    const textarea = screen.getByRole("textbox");
    await user.clear(textarea);
    await user.type(textarea, "User edited outline");
    resolveFile({ content: "Fetched outline" });

    await waitFor(() => {
      expect(textarea).toHaveValue("User edited outline");
    });
  });

  it("approves the edited outline", async () => {
    const user = userEvent.setup();
    vi.mocked(api.getWorkspaceFile).mockResolvedValue({ path: "draft/outline.md", content: "Fetched outline" });
    const onApproved = vi.fn().mockResolvedValue(undefined);

    render(
      <OutlineCard
        event={event}
        sessionId="session-1"
        taskId="task-1"
        onApproved={onApproved}
        onOpenPath={vi.fn()}
      />,
    );

    const textarea = await screen.findByRole("textbox");
    await user.clear(textarea);
    await user.type(textarea, "Approved local outline");
    await user.click(screen.getByRole("button", { name: /approve/i }));

    expect(api.approveOutline).toHaveBeenCalledWith("session-1", "Approved local outline");
    expect(onApproved).toHaveBeenCalledTimes(1);
  });

  it("does not overwrite dirty edits when the same outline event receives a summary update", async () => {
    const user = userEvent.setup();
    vi.mocked(api.getWorkspaceFile).mockResolvedValue({ path: "draft/outline.md", content: "Fetched outline" });
    const props = {
      event,
      sessionId: "session-1",
      taskId: "task-1",
      onApproved: vi.fn().mockResolvedValue(undefined),
      onOpenPath: vi.fn(),
    };
    const { rerender } = render(<OutlineCard {...props} />);

    const textarea = await screen.findByRole("textbox");
    await user.clear(textarea);
    await user.type(textarea, "User edited outline");

    rerender(
      <OutlineCard
        {...props}
        event={{
          ...event,
          summary: "Server pushed a fresher summary for the same event",
        }}
      />,
    );

    expect(textarea).toHaveValue("User edited outline");
  });
});
```

- [ ] **Step 4: Implement dirty edit protection**

In `apps/web/src/shell/conversation/cards/OutlineCard.tsx`, add a dirty ref:

```ts
const dirtyRef = useRef(false);
```

Import `useRef`:

```ts
import { useEffect, useRef, useState } from "react";
```

Change the fetch resolution:

```ts
.then((file) => {
  if (!cancelled && !dirtyRef.current) setOutline(file.content);
})
.catch(() => {
  if (!cancelled && !dirtyRef.current) setOutline(event.summary);
});
```

Change the textarea:

```tsx
<textarea
  value={outline}
  onChange={(event) => {
    dirtyRef.current = true;
    setOutline(event.target.value);
  }}
/>
```

Reset dirty state only when the event identity changes. Do not include `event.summary` in this dependency list because a summary refresh for the same event must not clear a user's dirty edit:

```ts
useEffect(() => {
  dirtyRef.current = false;
  setOutline(event.summary);
}, [event.id]);
```

- [ ] **Step 5: Run focused tests**

Run:

```powershell
cd apps/web
npm run test:unit -- src/shell/editor/__tests__/DraftEditor.test.tsx src/shell/conversation/cards/__tests__/OutlineCard.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Run typecheck for DraftEditor changes**

Run:

```powershell
cd apps/web
npm run test
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add apps/web/src/shell/editor/DraftEditor.tsx apps/web/src/shell/editor/__tests__/DraftEditor.test.tsx apps/web/src/shell/conversation/cards/OutlineCard.tsx apps/web/src/shell/conversation/cards/__tests__/OutlineCard.test.tsx
git commit -m "fix: stabilize editor and outline edits"
```

## Task 4: Stale Cross-Task Data And Panel Layout Sanitization

**Files:**
- Modify: `apps/web/src/shell/state/useDraft.ts`
- Modify: `apps/web/src/shell/state/useWorkspaceTree.ts`
- Modify: `apps/web/src/shell/AppShell.tsx`
- Modify: `apps/web/src/shell/state/useCollapse.ts`
- Modify: `apps/web/src/shell/__tests__/useCollapse.test.ts`
- Modify: `apps/web/src/shell/__tests__/AppShell.test.tsx`

- [ ] **Step 1: Remove cross-task placeholder data**

In `apps/web/src/shell/state/useDraft.ts`, remove the `keepPreviousData` import and the `placeholderData` field:

```ts
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";

export function useDraft(taskId: string | null | undefined) {
  return useQuery({
    queryKey: ["draft", taskId],
    queryFn: () => api.getDraft(taskId!),
    enabled: !!taskId,
    staleTime: 10_000,
  });
}
```

In `apps/web/src/shell/state/useWorkspaceTree.ts`, make the same change:

```ts
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";

export function useWorkspaceTree(taskId: string | null | undefined) {
  return useQuery({
    queryKey: ["workspace", taskId],
    queryFn: () => api.getWorkspace(taskId!),
    enabled: !!taskId,
    staleTime: 10_000,
  });
}
```

- [ ] **Step 2: Keep stale draft invisible while the active task draft loads**

In `apps/web/src/shell/AppShell.tsx`, compute the draft only from local edits or a successful query for the active task:

```ts
const activeTaskId = workspaces.activeTask?.id ?? null;
useEffect(() => {
  setLocalDraft(null);
}, [activeTaskId]);

const draftQueryTaskId = draftQuery.isSuccess ? activeTaskId : null;
const draft = localDraft ?? (draftQueryTaskId === activeTaskId ? draftQuery.data?.markdown : undefined) ?? "";
const draftTaskId = draftQueryTaskId;
```

- [ ] **Step 3: Add panel size helpers**

In `apps/web/src/shell/state/useCollapse.ts`, add:

```ts
export interface PanelLayout {
  left: number;
  center: number;
  right: number;
}

export function clampPanelSize(value: number, fallback: number, min: number, max: number) {
  if (!Number.isFinite(value)) return fallback;
  return Math.min(Math.max(value, min), max);
}

export function normalizePanelLayout(leftValue: number, rightValue: number): PanelLayout {
  const left = clampPanelSize(leftValue, 20, 12, 40);
  const right = clampPanelSize(rightValue, 32, 18, 48);
  const maxSideTotal = 82;
  const sideTotal = left + right;
  if (sideTotal <= maxSideTotal) {
    return { left, center: 100 - sideTotal, right };
  }
  const scale = maxSideTotal / sideTotal;
  const scaledLeft = Math.round(left * scale);
  const scaledRight = maxSideTotal - scaledLeft;
  return { left: scaledLeft, center: 18, right: scaledRight };
}
```

Use the helper in the hook:

```ts
const initialLayout = normalizePanelLayout(
  readNumber(STORAGE_KEYS.leftPanelSize, 20),
  readNumber(STORAGE_KEYS.rightPanelSize, 32),
);
const [leftPanelSize, setLeftPanelSize] = useState(initialLayout.left);
const [rightPanelSize, setRightPanelSize] = useState(initialLayout.right);
```

Update `rememberLayout`:

```ts
const rememberLayout = useCallback((layout: Record<string, number>) => {
  const normalized = normalizePanelLayout(layout.left ?? leftPanelSize, layout.right ?? rightPanelSize);
  setLeftPanelSize(normalized.left);
  setRightPanelSize(normalized.right);
  window.localStorage.setItem(STORAGE_KEYS.leftPanelSize, String(normalized.left));
  window.localStorage.setItem(STORAGE_KEYS.rightPanelSize, String(normalized.right));
}, [leftPanelSize, rightPanelSize]);
```

- [ ] **Step 4: Use normalized layout in AppShell**

In `apps/web/src/shell/AppShell.tsx`, compute once per render:

```ts
const panelLayout = {
  left: collapse.leftPanelSize,
  center: 100 - collapse.leftPanelSize - collapse.rightPanelSize,
  right: collapse.rightPanelSize,
};
```

Then pass:

```tsx
defaultLayout={panelLayout}
```

- [ ] **Step 5: Extend `useCollapse` tests**

In `apps/web/src/shell/__tests__/useCollapse.test.ts`, add:

```ts
import { normalizePanelLayout } from "../state/useCollapse";

it("normalizes persisted panel sizes so center remains visible", () => {
  expect(normalizePanelLayout(80, 80)).toEqual({ left: 37, center: 18, right: 45 });
  expect(normalizePanelLayout(Number.NaN, 999)).toEqual({ left: 20, center: 32, right: 48 });
});
```

- [ ] **Step 6: Run focused tests**

Run:

```powershell
cd apps/web
npm run test:unit -- src/shell/__tests__/useCollapse.test.ts src/shell/__tests__/AppShell.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add apps/web/src/shell/state/useDraft.ts apps/web/src/shell/state/useWorkspaceTree.ts apps/web/src/shell/AppShell.tsx apps/web/src/shell/state/useCollapse.ts apps/web/src/shell/__tests__/useCollapse.test.ts apps/web/src/shell/__tests__/AppShell.test.tsx
git commit -m "fix: prevent stale task data and invalid layouts"
```

## Task 5: Workspace Title Validation And Unknown Timeline Status

**Files:**
- Modify: `apps/web/src/shell/panes/WorkspacePane.tsx`
- Modify: `apps/web/src/shell/panes/__tests__/WorkspacePane.test.tsx`
- Verify: `apps/web/src/shell/AppShell.tsx`
- Verify: `apps/web/src/shell/state/useActiveWorkspace.ts`
- Modify: `apps/web/src/shell/assistant/docAgentAssistantMessages.ts`
- Modify: `apps/web/src/shell/assistant/__tests__/docAgentAssistantMessages.test.ts`

- [ ] **Step 1: Write title validation test**

In `apps/web/src/shell/panes/__tests__/WorkspacePane.test.tsx`, add:

```tsx
it("shows validation error when title is empty", async () => {
  const user = userEvent.setup();
  const onCreateWorkspace = vi.fn().mockResolvedValue(undefined);
  render(<WorkspacePane {...defaultProps} onCreateWorkspace={onCreateWorkspace} />);

  const openButtons = screen.getAllByRole("button", { name: /create workspace/i });
  await user.click(openButtons[0]);

  const form = screen.getByRole("form", { name: /create workspace/i });
  await user.clear(screen.getByLabelText("Title"));
  await user.type(screen.getByLabelText("Description"), "Build a search feature");
  await user.click(within(form).getByRole("button", { name: /create workspace/i }));

  await waitFor(() => {
    expect(screen.getByText(/title is required/i)).toBeTruthy();
  });

  expect(onCreateWorkspace).not.toHaveBeenCalled();
});
```

- [ ] **Step 2: Validate and render title errors**

In `apps/web/src/shell/panes/WorkspacePane.tsx`, change the schema:

```ts
const createWorkspaceSchema = z.object({
  title: z.string().trim().min(1, "Title is required"),
  description: z.string().trim().min(1, "Description is required"),
});
```

Render `errors.title` below the title input:

```tsx
{errors.title && (
  <p className="pane-note pane-note--error">{errors.title.message}</p>
)}
```

When submitting, pass the trimmed values:

```ts
await onCreateWorkspace(docTypeId, { title: values.title, description: values.description });
```

Zod `.trim()` already returns trimmed strings to `handleSubmit`.

- [ ] **Step 3: Verify workspace creation object contract**

Confirm `apps/web/src/shell/state/useActiveWorkspace.ts` still accepts object input:

```ts
mutationFn: async ({ docTypeId, input }: { docTypeId: string; input: { title: string; description: string } }) => {
  const task = await api.createTask(docTypeId, input);
  const session = await api.createSession(task.id);
  return { task, session };
},
```

Confirm the returned API still exposes the same object signature:

```ts
createWorkspace: (docTypeId: string, input: { title: string; description: string }) =>
  createWorkspaceMutation.mutateAsync({ docTypeId, input }),
```

Confirm `apps/web/src/shell/AppShell.tsx` does not collapse the object back into a string:

```tsx
onCreateWorkspace={async (docTypeId, brief) => {
  await workspaces.createWorkspace(docTypeId, brief);
}}
```

If any of those snippets differ on the implementation branch, update them to the snippets above before running the tests in this task.

- [ ] **Step 4: Write unknown timeline status test**

In `apps/web/src/shell/assistant/__tests__/docAgentAssistantMessages.test.ts`, add:

```ts
it("maps unknown timeline status to incomplete error instead of complete", () => {
  const messages = mapTimelineEventsToAssistantMessages([
    event({
      id: "evt-paused",
      kind: "agent_message",
      summary: "Paused by runtime",
      status: "paused" as TimelineEvent["status"],
    }),
  ]);

  expect(messages[0].status).toEqual({ type: "incomplete", reason: "error" });
});
```

- [ ] **Step 5: Implement unknown status fallback**

In `apps/web/src/shell/assistant/docAgentAssistantMessages.ts`, replace the old thread-status mapper with `assistantStatusFromTimelineStatus`, make the status mapper explicit, and update every call site in the file:

```ts
function assistantStatusFromTimelineStatus(status: string): NonNullable<ThreadMessage["status"]> {
  if (status === "pending" || status === "running") return { type: "running" };
  if (status === "failed") return { type: "incomplete", reason: "error" };
  if (status === "cancelled") return { type: "incomplete", reason: "cancelled" };
  if (status === "succeeded" || status === "skipped") return { type: "complete", reason: "stop" };
  return { type: "incomplete", reason: "error" };
}
```

Update both message-mapping call sites:

```ts
status: assistantStatusFromTimelineStatus(event.status),
```

After this change, the old mapper name must not appear anywhere in the file.

- [ ] **Step 6: Run focused tests**

Run:

```powershell
cd apps/web
npm run test:unit -- src/shell/panes/__tests__/WorkspacePane.test.tsx src/shell/assistant/__tests__/docAgentAssistantMessages.test.ts
npm run test
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add apps/web/src/shell/panes/WorkspacePane.tsx apps/web/src/shell/panes/__tests__/WorkspacePane.test.tsx apps/web/src/shell/assistant/docAgentAssistantMessages.ts apps/web/src/shell/assistant/__tests__/docAgentAssistantMessages.test.ts
git commit -m "fix: validate workspace titles and timeline status"
```

## Task 6: Guardrails For Future Component Integrations

**Files:**
- Create: `docs/quality/frontend-component-integration-checklist.md`
- Modify: `docs/quality/testing.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Create the checklist**

Create `docs/quality/frontend-component-integration-checklist.md`:

```markdown
# Frontend Component Integration Checklist

Use this checklist when adding or changing third-party React components in `apps/web`.

## Runtime Adapters

- Verify every callback required by the library runtime is either wired or intentionally documented as unsupported.
- Add a contract test for callbacks that can be triggered outside the visible UI, such as cancel, reload, retry, or submit.
- Keep async refs scoped by workspace, task, session, or tab when data can outlive the current render.

## Data Fetching

- Do not use `keepPreviousData` across task, session, workspace, or document boundaries unless the UI labels the data as stale and blocks writes.
- Key query invalidation by the same entity boundary used in the query key.
- Add a regression test for task switches when stale data could be shown or saved.

## DOM And Accessibility

- Do not nest interactive elements inside buttons, tabs, links, menu items, or tree rows.
- Verify keyboard dismissal for overlays, command menus, dialogs, and popovers.
- Add role-based Testing Library assertions for tabs, dialogs, menus, and forms.

## Persisted Layout State

- Clamp and normalize values loaded from localStorage before passing them to component defaults.
- Add tests for corrupted, missing, and extreme persisted values.
- Keep persisted state migrations local to the state helper that reads the values.

## Editor And Long-Lived Inputs

- Memoize CodeMirror extensions and listeners that are passed as arrays or objects.
- Protect dirty local edits from late async fetches.
- Prefer explicit dirty refs over inferring dirty state from text equality.

## Documentation Check

- When a new third-party component is introduced, link the relevant local type or documentation evidence in the review or plan.
- Record intentional deviations in `docs/decisions/` when they affect product behavior.
```

- [ ] **Step 2: Update testing guidance**

In `docs/quality/testing.md`, add this section after `## Test Shape`:

```markdown
## Frontend Component Integration

For `apps/web` changes that touch third-party React components or runtime adapters, add focused Vitest coverage for the component contract. Use `docs/quality/frontend-component-integration-checklist.md` to check runtime callbacks, entity-scoped async state, keyboard behavior, invalid DOM nesting, stale TanStack Query data, and persisted layout values.
```

- [ ] **Step 3: Add a small AGENTS.md pointer**

In `AGENTS.md`, add one working rule:

```markdown
- For `apps/web` changes that touch third-party React components, runtime adapters, editor widgets, overlays, or persisted UI layout, consult `docs/quality/frontend-component-integration-checklist.md` and add focused contract tests.
```

This is the right size for `AGENTS.md`: it changes the start-of-work behavior without embedding the full checklist in the root instruction file.

- [ ] **Step 4: Verify docs structure**

Run:

```powershell
Get-ChildItem -Recurse -File | Select-Object FullName
```

Expected: command exits 0.

- [ ] **Step 5: Commit**

```powershell
git add AGENTS.md docs/quality/testing.md docs/quality/frontend-component-integration-checklist.md
git commit -m "docs: add frontend integration guardrails"
```

## Task 7: Full Verification And Review Closure

**Files:**
- Modify: `docs/reviews/active/2026-05-13-plugin-component-lifecycle-audit.md`

- [ ] **Step 1: Run all frontend checks**

Run:

```powershell
cd apps/web
npm run test
npm run test:unit
npm run build
```

Expected: all commands exit 0.

- [ ] **Step 2: Run repository documentation structure check**

Run from the repository root:

```powershell
Get-ChildItem -Recurse -File | Select-Object FullName
```

Expected: command exits 0.

- [ ] **Step 3: Update the audit with closure status**

Append this section to `docs/reviews/active/2026-05-13-plugin-component-lifecycle-audit.md`:

```markdown
## Remediation status - 2026-05-13

Implemented fixes:

- ISSUE-01 and ISSUE-09: assistant-ui runtime cancellation is wired through the external store adapter and shares the same idempotent cancellation path as the composer button.
- ISSUE-02: imported attachment references are scoped by active task before submit.
- ISSUE-11 and ISSUE-14: CodeMirror extensions are memoized and outline edits are protected from late async fetches.
- ISSUE-12 and ISSUE-15: editor tabs avoid nested interactive controls and the command palette supports keyboard dismissal.
- ISSUE-16 and ISSUE-18: draft and workspace queries no longer show previous task data across task switches.
- ISSUE-19: persisted panel sizes are clamped and normalized before use.
- ISSUE-21: workspace title validation rejects empty strings.

Prevention:

- Added frontend component integration checklist in `docs/quality/frontend-component-integration-checklist.md`.
- Linked the checklist from `AGENTS.md`.
- Added focused Vitest coverage for runtime callbacks, scoped async state, a11y semantics, stale query data, persisted layout values, and form validation.

Verification:

- `cd apps/web; npm run test`
- `cd apps/web; npm run test:unit`
- `cd apps/web; npm run build`
- `Get-ChildItem -Recurse -File | Select-Object FullName`
```

- [ ] **Step 4: Commit**

```powershell
git add docs/reviews/active/2026-05-13-plugin-component-lifecycle-audit.md
git commit -m "docs: close component lifecycle audit"
```

## Rollback Or Recovery Notes

- Each task has its own commit. If a regression appears, use `git revert <commit>` for the affected task rather than reverting the whole sequence.
- If assistant-ui runtime typings reject the `onCancel` field, inspect `apps/web/node_modules/@assistant-ui/core/dist/runtimes/external-store/external-store-adapter.d.ts` and update the adapter object to match the installed type name.
- If `CommandPalette` Escape behavior conflicts with cmdk internals, move the Escape handler from the overlay to the `Command` root and keep the same test expectations.
- If the panel layout helper conflicts with `react-resizable-panels` constraints, adjust the helper constants so `left >= 12`, `right >= 18`, and `center >= 18` remain true.

## Verification Commands

Run before declaring the implementation complete:

```powershell
cd apps/web
npm run test
npm run test:unit
npm run build
```

Run from the repository root for documentation changes:

```powershell
Get-ChildItem -Recurse -File | Select-Object FullName
```

## Open Questions

- Should `unstable_capabilities: { copy: true }` remain inline, or should the runtime hook expose a named `DOC_AGENT_ASSISTANT_CAPABILITIES` constant with a comment tying it to assistant-ui 0.12.28?
- Should `useTimeline` redundant fetching be handled in this pass, or tracked as a separate performance cleanup after the lifecycle defects are fixed?
- Should the final audit closure move the review from `docs/reviews/active/` to a completed reviews folder if one is introduced?
