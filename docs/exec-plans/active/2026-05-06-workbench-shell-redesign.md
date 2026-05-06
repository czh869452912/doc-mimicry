# Workbench Shell Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current two-page React UI with one Codex-style three-column workbench shell using mature React primitives while preserving the existing FastAPI REST API, workspace contract, and semantic timeline contract.

**Architecture:** Keep backend and shared contracts unchanged. The new web UI is a library-composed shell: `react-resizable-panels` for layout, `react-arborist` for the workspace tree, `@assistant-ui/react` for chat thread/composer primitives, `@uiw/react-codemirror` for source editing, Radix/cmdk for overlays, and small DocAgent adapters for workspace state, timeline presentation, tabs, and slash commands.

**Tech Stack:** React 19, Vite 7, TypeScript 5.8, lucide-react, @assistant-ui/react 0.12.x, react-resizable-panels 4.x, react-arborist 3.x, @uiw/react-codemirror 4.x, CodeMirror 6, react-markdown, remark-gfm, rehype-sanitize, cmdk, Radix Dialog/Tabs/Tooltip, diff/jsdiff.

---

## Goal

Build the redesigned Workbench shell from `docs/superpowers/specs/2026-05-06-workbench-shell-redesign-design.md` as a UI-only migration.

The finished branch should let a user:

1. Open the app into a single three-column shell.
2. Create and switch workspaces and sessions from a left tree.
3. Use a center conversation stream with user messages, agent messages, event pills, inline cards, slash commands, and a composer.
4. View and edit the workspace draft in a pinned Draft tab on the right.
5. Open files, versions, diffs, and artifacts as additional right-panel tabs.
6. Open document type management from a settings drawer.
7. Collapse and resize side panels with state persisted in `localStorage`.

## Scope

- Replace `apps/web/src/pages/WorkbenchPage.tsx` and `apps/web/src/pages/ManagementPage.tsx` with `apps/web/src/shell/**`.
- Update `apps/web/src/App.tsx` to mount the new shell directly.
- Update `apps/web/src/styles.css` by moving design tokens and shell styles into focused CSS files under `apps/web/src/shell/theme/`.
- Install the new frontend dependencies listed in the spec.
- Add a small TypeScript test harness for pure state/mapping helpers.
- Add a Playwright smoke test for shell mount, workspace tree, composer submit, and draft auto-save.
- Keep `apps/web/src/api.ts`, existing REST endpoints, backend code, runtime adapters, workspace contract, and timeline contract unchanged unless a compiler error proves a type-only frontend adjustment is needed.

## Non-Goals

- No backend endpoints, database, workspace layout, runtime adapter, or timeline mapper changes.
- No SSE/WebSocket streaming.
- No dark mode.
- No mobile optimization beyond avoiding broken overflow.
- No shadcn/ui pre-styled component set or Tailwind migration.
- No rich WYSIWYG editor.
- No file drag-and-drop upload in this plan.
- No explicit checkpoint endpoint. The `+ Checkpoint` affordance is disabled with explanatory title text unless an existing safe endpoint is available.

## Files And Modules Likely To Change

### Modify

- `apps/web/package.json`: add runtime dependencies and Playwright/Vitest test scripts if absent.
- `apps/web/package-lock.json`: update through `npm install`.
- `apps/web/src/App.tsx`: replace page switcher with `<AppShell />`.
- `apps/web/src/types.ts`: add frontend-only tab, presentation, and helper types only if keeping them centralized is cleaner than local shell types.
- `apps/web/src/styles.css`: reduce to importing shell theme CSS or replace with global reset styles.

### Delete At The End

- `apps/web/src/pages/WorkbenchPage.tsx`
- `apps/web/src/pages/ManagementPage.tsx`

### Create

- `apps/web/src/shell/AppShell.tsx`: top-level state wiring, panel layout, selected workspace/session, drawer/palette state.
- `apps/web/src/shell/TopBar.tsx`: 36px top bar, status dot, command palette trigger, settings trigger.
- `apps/web/src/shell/SettingsDrawer.tsx`: Radix Dialog sheet replacing the old Management page.
- `apps/web/src/shell/CommandPalette.tsx`: cmdk command palette using the shared slash command registry.
- `apps/web/src/shell/panes/WorkspacePane.tsx`: left tree using react-arborist.
- `apps/web/src/shell/panes/ConversationPane.tsx`: center stream and composer.
- `apps/web/src/shell/panes/EditorPane.tsx`: right tab shell.
- `apps/web/src/shell/conversation/docagentRuntime.ts`: REST/polling bridge and timeline event merge store.
- `apps/web/src/shell/conversation/timelinePresentation.ts`: pure `TimelineEvent -> Presentation` mapper.
- `apps/web/src/shell/conversation/slashCommands.ts`: registry for composer slash menu and command palette.
- `apps/web/src/shell/conversation/cards/OutlineCard.tsx`
- `apps/web/src/shell/conversation/cards/ChecklistCard.tsx`
- `apps/web/src/shell/conversation/cards/ArtifactCard.tsx`
- `apps/web/src/shell/conversation/cards/ApprovalCard.tsx`
- `apps/web/src/shell/editor/DraftEditor.tsx`
- `apps/web/src/shell/editor/MarkdownPreview.tsx`
- `apps/web/src/shell/editor/DiffViewer.tsx`
- `apps/web/src/shell/editor/tabs/DraftTab.tsx`
- `apps/web/src/shell/editor/tabs/FileTab.tsx`
- `apps/web/src/shell/editor/tabs/VersionTab.tsx`
- `apps/web/src/shell/editor/tabs/DiffTab.tsx`
- `apps/web/src/shell/editor/tabs/ArtifactTab.tsx`
- `apps/web/src/shell/editor/useTabs.ts`
- `apps/web/src/shell/editor/useAutoSave.ts`
- `apps/web/src/shell/state/useWorkspaces.ts`
- `apps/web/src/shell/state/useTimeline.ts`
- `apps/web/src/shell/state/useCollapse.ts`
- `apps/web/src/shell/theme/tokens.css`
- `apps/web/src/shell/theme/reset.css`
- `apps/web/src/shell/theme/typography.css`
- `apps/web/src/shell/theme/assistant-ui.css`
- `apps/web/src/shell/theme/shell.css`
- `apps/web/src/shell/__tests__/timelinePresentation.test.ts`
- `apps/web/src/shell/__tests__/docagentRuntime.test.ts`
- `apps/web/src/shell/__tests__/useTabs.test.ts`
- `apps/web/tests/workbench-shell.spec.ts`

## Step-By-Step Implementation Checklist

### Task 1: Install Dependencies And Test Harness

**Files:**
- Modify: `apps/web/package.json`
- Modify: `apps/web/package-lock.json`
- Create: `apps/web/vitest.config.ts`
- Create: `apps/web/tests/workbench-shell.spec.ts`

- [ ] Step 1: Install runtime dependencies.

Run from `apps/web`:

```powershell
npm install @assistant-ui/react react-resizable-panels react-arborist @uiw/react-codemirror codemirror @codemirror/lang-markdown @codemirror/state @codemirror/view react-markdown remark-gfm rehype-sanitize cmdk @radix-ui/react-dialog @radix-ui/react-tabs @radix-ui/react-tooltip diff
```

Expected: install exits 0 and `package.json` includes the new dependencies.

- [ ] Step 2: Install test dependencies.

Run from `apps/web`:

```powershell
npm install -D vitest @testing-library/react @testing-library/user-event @testing-library/jest-dom jsdom @playwright/test
```

Expected: install exits 0 and `package.json` includes the new dev dependencies.

- [ ] Step 3: Update scripts in `apps/web/package.json`.

Add or preserve these scripts:

```json
{
  "scripts": {
    "dev": "vite --host 127.0.0.1",
    "build": "tsc --noEmit && vite build",
    "test": "tsc --noEmit",
    "test:unit": "vitest run",
    "test:e2e": "playwright test"
  }
}
```

- [ ] Step 4: Create `apps/web/vitest.config.ts`.

```ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: [],
  },
});
```

- [ ] Step 5: Add a placeholder Playwright smoke test that can be expanded after the shell exists.

Create `apps/web/tests/workbench-shell.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

test("workbench shell smoke placeholder", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("body")).toBeVisible();
});
```

- [ ] Step 6: Verify dependency compatibility.

Run from `apps/web`:

```powershell
npm run build
npm run test:unit
```

Expected: `npm run build` exits 0; `npm run test:unit` exits 0 with the current placeholder/no tests.

- [ ] Step 7: Commit.

```powershell
git add apps/web/package.json apps/web/package-lock.json apps/web/vitest.config.ts apps/web/tests/workbench-shell.spec.ts
git commit -m "chore(web): add shell redesign dependencies"
```

### Task 2: Add Theme Tokens And Shell Scaffold

**Files:**
- Create: `apps/web/src/shell/theme/tokens.css`
- Create: `apps/web/src/shell/theme/reset.css`
- Create: `apps/web/src/shell/theme/typography.css`
- Create: `apps/web/src/shell/theme/assistant-ui.css`
- Create: `apps/web/src/shell/theme/shell.css`
- Create: `apps/web/src/shell/AppShell.tsx`
- Create: `apps/web/src/shell/TopBar.tsx`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/styles.css`

- [ ] Step 1: Create design token CSS in `tokens.css`.

Use CSS variables for the Cursor warm-cream tokens from the spec:

```css
:root {
  --color-canvas: #f7f7f4;
  --color-canvas-soft: #fafaf7;
  --color-surface-card: #ffffff;
  --color-surface-strong: #e6e5e0;
  --color-ink: #26251e;
  --color-body: #5a5852;
  --color-muted: #807d72;
  --color-hairline: #e6e5e0;
  --color-hairline-strong: #cfcdc4;
  --color-primary: #f54e00;
  --color-success: #278a4b;
  --color-error: #ba2f2f;
  --color-timeline-thinking: #ffe2d2;
  --color-timeline-grep: #dff3e8;
  --color-timeline-read: #dcecff;
  --color-timeline-edit: #ebe3ff;
  --color-timeline-done: #fff0bf;
  --font-body: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-code: "JetBrains Mono", "Cascadia Mono", Consolas, monospace;
  --radius-md: 8px;
  --radius-lg: 12px;
}
```

- [ ] Step 2: Create `reset.css`, `typography.css`, `assistant-ui.css`, and `shell.css`.

Keep the first shell styles minimal: full-height app, 36px top bar, three placeholder panels, icon buttons, focus ring, and token-based colors.

- [ ] Step 3: Create `TopBar.tsx`.

It accepts `workspaceLabel`, `sessionLabel`, `status`, `onOpenCommandPalette`, and `onOpenSettings`.

- [ ] Step 4: Create `AppShell.tsx` with `react-resizable-panels`.

Initial content can be placeholders:

```tsx
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { useState } from "react";
import { TopBar } from "./TopBar";

export function AppShell() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);

  return (
    <main className="docagent-shell">
      <TopBar
        workspaceLabel="No workspace"
        sessionLabel="no session"
        status="idle"
        onOpenCommandPalette={() => setCommandOpen(true)}
        onOpenSettings={() => setSettingsOpen(true)}
      />
      <PanelGroup direction="horizontal" className="docagent-shell__panels">
        <Panel defaultSize={20} minSize={12} collapsible>
          <aside className="shell-panel">Workspace</aside>
        </Panel>
        <PanelResizeHandle className="resize-handle" />
        <Panel minSize={32}>
          <section className="shell-panel shell-panel--center">Conversation</section>
        </Panel>
        <PanelResizeHandle className="resize-handle" />
        <Panel defaultSize={32} minSize={18} collapsible>
          <aside className="shell-panel">Draft</aside>
        </Panel>
      </PanelGroup>
      {settingsOpen && <div hidden>settings-open</div>}
      {commandOpen && <div hidden>command-open</div>}
    </main>
  );
}
```

- [ ] Step 5: Replace `App.tsx`.

```tsx
import { AppShell } from "./shell/AppShell";
import "./styles.css";

export function App() {
  return <AppShell />;
}
```

- [ ] Step 6: Replace `styles.css` with imports.

```css
@import "./shell/theme/tokens.css";
@import "./shell/theme/reset.css";
@import "./shell/theme/typography.css";
@import "./shell/theme/assistant-ui.css";
@import "./shell/theme/shell.css";
```

- [ ] Step 7: Verify bootable scaffold.

Run from `apps/web`:

```powershell
npm run build
```

Expected: build exits 0 and the app renders a top bar plus three placeholder panels.

- [ ] Step 8: Commit.

```powershell
git add apps/web/src/App.tsx apps/web/src/styles.css apps/web/src/shell
git commit -m "feat(web): scaffold workbench shell"
```

### Task 3: Add Workspace State And Left Tree

**Files:**
- Create: `apps/web/src/shell/state/useWorkspaces.ts`
- Create: `apps/web/src/shell/panes/WorkspacePane.tsx`
- Modify: `apps/web/src/shell/AppShell.tsx`

- [ ] Step 1: Implement `useWorkspaces.ts`.

Responsibilities:

- Load doc types and tasks with `api.listDocTypes()` and `api.listTasks()`.
- Track `activeTask`, `activeSession`, `workspaceTree`, and `sessions`.
- Persist last selected task/session ids in `localStorage`.
- Provide `createWorkspace(docTypeId, brief)`, `selectTask(task)`, `selectSession(session)`, `ensureSession()`, and `refreshActiveWorkspace()`.

- [ ] Step 2: Add unit tests for `latestByUpdatedAt` and tree data flattening.

Create pure helpers in `useWorkspaces.ts`:

```ts
export function latestByUpdatedAt<T extends { updated_at: string }>(items: T[]): T | null {
  return [...items].sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at))[0] ?? null;
}
```

Test expected latest item and empty list behavior.

- [ ] Step 3: Implement `WorkspacePane.tsx` with `react-arborist`.

Tree node ids should be stable:

- task node: `task:${task.id}`
- session node: `session:${session.id}`
- folder node: `folder:${task.id}:${folderName}`
- file node: `file:${task.id}:${path}`

Folder roots: `versions`, `inputs`, `context`, `draft`, `reviews`, `artifacts`.

- [ ] Step 4: Wire `WorkspacePane` into `AppShell.tsx`.

The left panel should show:

- `WORKSPACES` label.
- `+` button opening a small create form.
- Active workspace/session highlighting.
- Empty state card if no tasks exist.

- [ ] Step 5: Verify.

Run from `apps/web`:

```powershell
npm run test:unit
npm run build
```

Expected: unit tests pass and build exits 0.

- [ ] Step 6: Commit.

```powershell
git add apps/web/src/shell/state/useWorkspaces.ts apps/web/src/shell/panes/WorkspacePane.tsx apps/web/src/shell/AppShell.tsx apps/web/src/shell/__tests__
git commit -m "feat(web): add workspace tree pane"
```

### Task 4: Add Right Editor Tabs, Markdown Preview, Diff, And Auto-Save

**Files:**
- Create: `apps/web/src/shell/editor/useTabs.ts`
- Create: `apps/web/src/shell/editor/useAutoSave.ts`
- Create: `apps/web/src/shell/editor/DraftEditor.tsx`
- Create: `apps/web/src/shell/editor/MarkdownPreview.tsx`
- Create: `apps/web/src/shell/editor/DiffViewer.tsx`
- Create: `apps/web/src/shell/editor/tabs/DraftTab.tsx`
- Create: `apps/web/src/shell/editor/tabs/FileTab.tsx`
- Create: `apps/web/src/shell/editor/tabs/VersionTab.tsx`
- Create: `apps/web/src/shell/editor/tabs/DiffTab.tsx`
- Create: `apps/web/src/shell/editor/tabs/ArtifactTab.tsx`
- Create: `apps/web/src/shell/panes/EditorPane.tsx`
- Modify: `apps/web/src/shell/AppShell.tsx`

- [ ] Step 1: Implement `useTabs.ts`.

Tab types:

```ts
export type EditorTab =
  | { id: "draft"; kind: "draft"; title: "Draft"; pinned: true }
  | { id: string; kind: "file"; title: string; path: string; content: string }
  | { id: string; kind: "version"; title: string; path: string; content: string }
  | { id: string; kind: "diff"; title: string; leftTitle: string; rightTitle: string; left: string; right: string }
  | { id: string; kind: "artifact"; title: string; path: string; content: string };
```

Helpers must keep the Draft tab pinned and dedupe tabs by `id`.

- [ ] Step 2: Implement `MarkdownPreview.tsx`.

Use:

```tsx
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";
```

Render markdown with `remarkPlugins={[remarkGfm]}` and `rehypePlugins={[rehypeSanitize]}`.

- [ ] Step 3: Implement `DraftEditor.tsx` with `@uiw/react-codemirror`.

Use `markdown()` from `@codemirror/lang-markdown`, `lineWrapping`, `basicSetup`, and token-based class names.

- [ ] Step 4: Implement `useAutoSave.ts`.

Behavior:

- Debounce `api.updateDraft(taskId, markdown)` by 800ms.
- Expose `saveState: "idle" | "saving" | "saved" | "error"`.
- Do not save if no `taskId`.
- Cancel pending timer on unmount.

- [ ] Step 5: Implement `DraftTab.tsx`.

Draft tab features:

- Preview/source toggle.
- Disabled `+ Checkpoint` button with title `Checkpoint endpoint is not available yet`.
- Last save state text.
- Selection mini-bar actions: send selection to composer and revise selection via existing `api.reviseSelection`.

- [ ] Step 6: Implement file/version/artifact tabs.

Use read-only CodeMirror for non-Markdown files and `MarkdownPreview` for `.md` content.

- [ ] Step 7: Implement `DiffViewer.tsx`.

Use `diffLines` from `diff` to render two panes with inserted/deleted/unchanged rows. Keep line-level diff only for Phase 1.

- [ ] Step 8: Wire `EditorPane` into `AppShell.tsx`.

Clicking a file node in `WorkspacePane` should call `api.getWorkspaceFile(task.id, path)` and open the appropriate tab.

- [ ] Step 9: Verify.

Run from `apps/web`:

```powershell
npm run test:unit
npm run build
```

Expected: unit tests pass and build exits 0.

- [ ] Step 10: Commit.

```powershell
git add apps/web/src/shell/editor apps/web/src/shell/panes/EditorPane.tsx apps/web/src/shell/AppShell.tsx
git commit -m "feat(web): add tabbed draft editor"
```

### Task 5: Add Timeline Presentation And Runtime Merge Store

**Files:**
- Create: `apps/web/src/shell/conversation/timelinePresentation.ts`
- Create: `apps/web/src/shell/conversation/docagentRuntime.ts`
- Create: `apps/web/src/shell/__tests__/timelinePresentation.test.ts`
- Create: `apps/web/src/shell/__tests__/docagentRuntime.test.ts`
- Modify: `apps/web/src/shell/state/useTimeline.ts`

- [ ] Step 1: Implement `timelinePresentation.ts`.

Use exact current `SemanticEventKind` string values:

```ts
export type Presentation =
  | { kind: "message"; role: "user" | "agent"; body: string }
  | { kind: "pill"; category: "thinking" | "grep" | "read" | "edit" | "done"; summary: string; meta?: string }
  | { kind: "card"; cardType: "outline" | "checklist" | "approval" | "artifact"; payload: TimelineEvent };
```

Mapping:

- `user_message` -> user message
- `agent_message` -> agent message
- `read_skill`, `convert_input` -> read pill
- `analyze_examples` -> grep pill
- `build_context`, `extract_style`, `extract_structure`, `generate_outline`, `propose_outline` -> edit pill, with `propose_outline` producing an outline card when `paths` contains `draft/outline.md`
- `approve_outline`, `run_checklist`, `export_markdown`, `export_docx`, `export_pdf`, `approval_resolved` -> done pill or card where applicable
- `approval_requested` -> approval card
- `update_draft`, `revise_selection`, `create_checkpoint` -> edit pill
- `error` -> thinking pill with failed styling derived from `event.status`
- unknown -> thinking pill with raw kind visible

- [ ] Step 2: Add unit tests for all enum values.

Test file must include one sample event for every string from `SemanticEventKind` in `packages/contracts/docagent_contracts/models.py`.

- [ ] Step 3: Implement event merge helpers in `docagentRuntime.ts`.

Pure helper:

```ts
export function mergeTimelineEvents(existing: TimelineEvent[], incoming: TimelineEvent[]): TimelineEvent[] {
  const byId = new Map<string, TimelineEvent>();
  for (const event of existing) byId.set(event.id, event);
  for (const event of incoming) byId.set(event.id, event);
  return [...byId.values()];
}
```

Preserve backend order by rebuilding from incoming order when a full refresh is available:

```ts
export function replaceWithIdDedup(incoming: TimelineEvent[]): TimelineEvent[] {
  const seen = new Set<string>();
  return incoming.filter((event) => {
    if (seen.has(event.id)) return false;
    seen.add(event.id);
    return true;
  });
}
```

- [ ] Step 4: Add tests for duplicate prevention.

Input with duplicate ids should produce one event per id and keep the last payload for that id.

- [ ] Step 5: Create `useTimeline.ts`.

It should fetch `api.getTimeline(sessionId)`, apply id dedupe, expose `events`, `presentations`, `refreshTimeline()`, and `resetTimeline()`.

- [ ] Step 6: Verify.

Run from `apps/web`:

```powershell
npm run test:unit
npm run build
```

Expected: tests pass and build exits 0.

- [ ] Step 7: Commit.

```powershell
git add apps/web/src/shell/conversation/timelinePresentation.ts apps/web/src/shell/conversation/docagentRuntime.ts apps/web/src/shell/state/useTimeline.ts apps/web/src/shell/__tests__
git commit -m "feat(web): map timeline events to conversation presentations"
```

### Task 6: Add Conversation Pane, Inline Cards, Composer, And Slash Commands

**Files:**
- Create: `apps/web/src/shell/panes/ConversationPane.tsx`
- Create: `apps/web/src/shell/conversation/slashCommands.ts`
- Create: `apps/web/src/shell/conversation/cards/OutlineCard.tsx`
- Create: `apps/web/src/shell/conversation/cards/ChecklistCard.tsx`
- Create: `apps/web/src/shell/conversation/cards/ArtifactCard.tsx`
- Create: `apps/web/src/shell/conversation/cards/ApprovalCard.tsx`
- Modify: `apps/web/src/shell/AppShell.tsx`

- [ ] Step 1: Implement `slashCommands.ts`.

Registry entries:

- `/start` -> ensure session, `api.startLoop(session.id)`, refresh workspace and timeline
- `/check` -> `api.runChecklist(session.id)`, refresh timeline
- `/export` -> `api.exportMarkdown(session.id)`, refresh timeline, open artifact tab
- `/files` -> focus/open file list tab
- `/versions` -> open versions view
- `/diff <vA> <vB>` -> open diff tab if both files can be loaded
- `/help` -> inject local help card

Do not implement `/checkpoint` as a backend call. It returns a local disabled/help presentation explaining no endpoint exists yet.

- [ ] Step 2: Implement inline cards.

Cards consume a source `TimelineEvent` payload and callbacks:

- `OutlineCard`: loads `draft/outline.md` if needed, lets user edit local outline, calls `api.approveOutline(session.id, outline)`.
- `ChecklistCard`: opens `reviews/checklist_result.md` if path exists.
- `ArtifactCard`: opens artifact path in editor.
- `ApprovalCard`: displays summary and available action if the backend event requires a known action.

- [ ] Step 3: Implement `ConversationPane.tsx`.

Use `@assistant-ui/react` for composer/thread primitives where stable. If custom data/tool rendering is too constrained, use assistant-ui composer primitives and render the presentation list directly in a DocAgent stream container. Record the fallback in the active plan before continuing.

Required behavior:

- Stream shows user messages, agent messages, event pills, and inline cards in timeline order.
- Composer auto-grows to about 6 lines.
- Enter sends; Shift+Enter inserts newline.
- Leading slash parses against `slashCommands.ts`.
- Unknown slash input sends as plain text.
- If no active session exists, first message creates one with `api.createSession(task.id)`.
- After each action, refresh timeline and workspace state.

- [ ] Step 4: Wire `ConversationPane` into `AppShell.tsx`.

Pass active task/session state, `ensureSession`, `refreshActiveWorkspace`, `refreshTimeline`, and editor tab open callbacks.

- [ ] Step 5: Verify.

Run from `apps/web`:

```powershell
npm run test:unit
npm run build
```

Expected: tests pass and build exits 0.

- [ ] Step 6: Commit.

```powershell
git add apps/web/src/shell/panes/ConversationPane.tsx apps/web/src/shell/conversation apps/web/src/shell/AppShell.tsx
git commit -m "feat(web): add conversation stream and composer"
```

### Task 7: Add Command Palette, Settings Drawer, Collapse Persistence, And Empty States

**Files:**
- Create: `apps/web/src/shell/CommandPalette.tsx`
- Create: `apps/web/src/shell/SettingsDrawer.tsx`
- Create: `apps/web/src/shell/state/useCollapse.ts`
- Modify: `apps/web/src/shell/AppShell.tsx`
- Modify: `apps/web/src/shell/TopBar.tsx`
- Modify: `apps/web/src/shell/panes/WorkspacePane.tsx`
- Modify: `apps/web/src/shell/panes/ConversationPane.tsx`
- Modify: `apps/web/src/shell/panes/EditorPane.tsx`

- [ ] Step 1: Implement `useCollapse.ts`.

Persist:

- `docagent:leftPanelSize`
- `docagent:rightPanelSize`
- `docagent:leftCollapsed`
- `docagent:rightCollapsed`
- `docagent:draftTabMode`
- `docagent:lastTaskId`
- `docagent:lastSessionId`

- [ ] Step 2: Implement `CommandPalette.tsx`.

Use `cmdk` and the shared slash command registry. It should open on the top bar trigger and keyboard shortcut `Ctrl+K` or `Meta+K`.

- [ ] Step 3: Implement `SettingsDrawer.tsx`.

Use Radix Dialog in non-modal sheet pattern. Content should replace the old `ManagementPage`:

- Document Types list.
- Selected document type resource groups.
- SKILL.md preview.
- Skill Creator placeholder.
- Runtime read-only section.

- [ ] Step 4: Add empty/loading/error states.

Required states:

- No workspaces.
- Workspace selected, no session.
- Workspace selected, no draft.
- Timeline refresh error.
- Draft save error.

- [ ] Step 5: Wire panel collapse behavior.

Use `react-resizable-panels` collapsible panels. Rail icons:

- left: workspace list, active session, new workspace
- right: draft, file list, versions

Clicking a rail icon opens overlay behavior only if straightforward with the current panel API. If overlay would force brittle code, use expand-on-click for Phase 1 and note overlay as follow-up in the plan.

- [ ] Step 6: Verify.

Run from `apps/web`:

```powershell
npm run test:unit
npm run build
```

Expected: tests pass and build exits 0.

- [ ] Step 7: Commit.

```powershell
git add apps/web/src/shell/CommandPalette.tsx apps/web/src/shell/SettingsDrawer.tsx apps/web/src/shell/state/useCollapse.ts apps/web/src/shell
git commit -m "feat(web): add shell overlays and persisted panels"
```

### Task 8: Replace Old Pages, Add Smoke Coverage, And Final Verification

**Files:**
- Delete: `apps/web/src/pages/WorkbenchPage.tsx`
- Delete: `apps/web/src/pages/ManagementPage.tsx`
- Modify: `apps/web/tests/workbench-shell.spec.ts`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/styles.css`
- Modify: `apps/web/README.md` if verification commands change

- [ ] Step 1: Delete old pages.

Remove `apps/web/src/pages/` after `App.tsx` no longer imports it.

- [ ] Step 2: Expand Playwright smoke test.

Smoke steps:

```ts
import { expect, test } from "@playwright/test";

test("workbench shell supports the phase 1 happy path", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("DocAgent")).toBeVisible();
  await page.getByRole("button", { name: /create/i }).click();
  await page.getByRole("textbox", { name: /brief/i }).fill("Write a PRD for the first usable document imitation loop.");
  await page.getByRole("button", { name: /create workspace/i }).click();
  await expect(page.getByText(/session/i)).toBeVisible();
  await page.getByRole("textbox", { name: /message/i }).fill("/start");
  await page.keyboard.press("Enter");
  await expect(page.getByText(/outline/i)).toBeVisible();
});
```

Adjust selectors to final accessible names; keep the user-level behavior unchanged.

- [ ] Step 3: Run full frontend verification.

Run from `apps/web`:

```powershell
npm run build
npm run test:unit
```

Expected: both commands exit 0.

- [ ] Step 4: Run backend/API regression tests because the UI still relies on existing endpoints.

Run from repo root:

```powershell
python -m pytest packages/contracts/tests packages/workspace/tests packages/timeline/tests tools/import/tests services/api/tests agent/runtime-adapters/mock/tests tests -q
```

Expected: all selected Python tests pass.

- [ ] Step 5: Run dev smoke manually.

Run from repo root:

```powershell
.\start-dev.cmd
```

Open `http://127.0.0.1:5173` and verify:

1. Create a workspace.
2. Send a plain message.
3. Run `/start`.
4. Edit and approve outline card.
5. Run `/check`.
6. Run `/export`.
7. Open files/versions/diff from the right panel.
8. Open settings drawer.
9. Collapse and resize side panels, reload, and confirm persisted state.

- [ ] Step 6: Run Playwright smoke if the dev server is available.

From `apps/web`:

```powershell
npm run test:e2e
```

Expected: smoke test passes. If Playwright browser binaries are missing, install with `npx playwright install chromium` and rerun.

- [ ] Step 7: Final commit.

```powershell
git add apps/web docs/exec-plans/active/2026-05-06-workbench-shell-redesign.md
git commit -m "feat(web): replace pages with workbench shell"
```

## Verification Commands

Documentation-only check after writing or updating this plan:

```powershell
Get-ChildItem -Recurse -File | Select-Object FullName
```

Frontend:

```powershell
cd apps/web
npm run build
npm run test:unit
npm run test:e2e
```

Backend/API regression:

```powershell
python -m pytest packages/contracts/tests packages/workspace/tests packages/timeline/tests tools/import/tests services/api/tests agent/runtime-adapters/mock/tests tests -q
```

Manual smoke:

```powershell
.\start-dev.cmd
```

Then test `http://127.0.0.1:5173` with the seven-step smoke path from the design spec.

## Rollback Or Recovery Notes

- If the new dependency set breaks React 19 compatibility, revert Task 1 and choose the smallest compatible subset before proceeding.
- If `@assistant-ui/react` custom data/tool rendering blocks the timeline card model, keep assistant-ui for composer primitives and render the stream with DocAgent components. Record the reason in this plan before continuing.
- If CodeMirror bundle size becomes a problem, keep `MarkdownPreview` and temporarily replace source mode with a textarea while preserving the `DraftEditor` interface.
- If `react-resizable-panels` overlay behavior is brittle, ship expand-on-click rails first and keep overlay panels as a follow-up.
- If Playwright installation is unavailable on the machine, keep unit tests plus manual browser smoke as the blocking verification and record the missing binary reason in the final implementation notes.
- To recover the old UI during implementation, restore `App.tsx` imports of `pages/WorkbenchPage.tsx` and `pages/ManagementPage.tsx` before Task 8 deletes those files.

## Open Questions

- `+ Checkpoint` has no safe explicit endpoint in the current API. This plan disables the button and documents the gap rather than piggybacking on `PUT /tasks/{id}/draft`.
- The design asks for temporary panel overlays from collapsed rails. This plan treats that as best-effort and allows expand-on-click if overlay behavior adds fragile complexity.
- The exact assistant-ui extension point must be confirmed in implementation. The fallback is explicitly allowed: assistant-ui composer + DocAgent-rendered stream.
- The current `TimelineEvent` frontend type lacks `created_at`; this plan preserves backend list order and does not add a contract field.
- The old `ManagementPage` has read-only doc type details only. Skill Creator remains a placeholder in the settings drawer.

