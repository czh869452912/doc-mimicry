# Plugin Component Lifecycle Audit — 2026-05-13

Scope: `apps/web` — `@assistant-ui/react` (0.12.28), `react-resizable-panels` (4.11.0), `@tanstack/react-router`, `@tanstack/react-query`.
Each entry is appended as discovered. Severity: **Critical / Major / Minor / Info**.

## Re-review update - 2026-05-13

Reader: an engineer preparing the next fix pass.

Post-read action: decide which component lifecycle/integration issues to fix first without re-validating stale findings.

Re-check method:

- Context7 resources were not available in this Codex environment.
- Cross-checked local source against installed package types/source under `apps/web/node_modules`.
- Cross-checked public docs where available: assistant-ui external store runtime/message primitives, Radix Tabs/Dialog, TanStack Query placeholder data, react-resizable-panels, and react-arborist.

Status after re-check:

- Confirmed: ISSUE-01, ISSUE-02, ISSUE-03, ISSUE-04, ISSUE-06, ISSUE-07, ISSUE-08, ISSUE-09, ISSUE-10, ISSUE-11, ISSUE-12, ISSUE-14, ISSUE-15, ISSUE-17.
- Confirmed with corrected wording: ISSUE-13 and ISSUE-16.
- Retracted: ISSUE-05.
- Newly added: ISSUE-18, ISSUE-19, ISSUE-20.

## Third-pass audit update — 2026-05-13

Scope extended to: `DiffViewer.tsx` (react-diff-viewer-continued), `WorkspacePane.tsx` (react-hook-form + zod), `slashCommands.ts`, `api.ts`, `App.tsx` (@tanstack/react-router), `QueryClient` setup (main.tsx), `useCollapse` test coverage, AppShell auto-save test coverage.

Cross-check method: local `node_modules` type inspection for `react-diff-viewer-continued`, `cmdk`, `@hookform/resolvers/zod`, `@tanstack/react-router`; source-read of all remaining untouched files; test-suite scan for coverage gaps.

Findings:
- ISSUE-18, ISSUE-19, ISSUE-20: all three independently verified against source.
- ISSUE-16 partial mitigation confirmed: `AppShell.test.tsx:142` ("does not autosave the previous task draft into a newly selected task while that draft loads") covers the strongest regression path. The stale-UI display window remains unguarded.
- `DiffViewer.tsx` style overrides: `wordAddedBackground`/`wordRemovedBackground` match `ReactDiffViewerStylesVariables` type — correct.
- `react-diff-viewer-continued` `leftTitle`/`rightTitle`/`oldValue`/`newValue` props: all confirmed valid in installed package types.
- `DiffMethod.WORDS` enum value: confirmed (`"diffWords"`) in installed package.
- `@tanstack/react-router` usage: `validateSearch`, `useNavigate({ from: "/" })`, `useSearch({ from: "/" })`, route tree structure — all correct.
- `@tanstack/react-query` `QueryClient` no custom `retry`/`staleTime` defaults: queries inherit 3-retry default; individual queries each override `staleTime` appropriately — acceptable.
- `react-hook-form` + `zodResolver` wiring: correct; validation runs on submit.
- New finding: ISSUE-21 (zod schema `title` field accepts empty string).
- No new issues in: `slashCommands.ts`, `api.ts`, `ErrorBoundary`, `TopBar`, card components (ApprovalCard, ArtifactCard, ChecklistCard), `LazyDraftEditor`/`Suspense` boundary, `MarkdownPreview` (rehype-sanitize default schema is compatible with remark-gfm output).

Recommended fix order:

1. ISSUE-01 / ISSUE-09: wire cancellation through assistant-ui runtime and make cancel idempotent.
2. ISSUE-02 / ISSUE-03: scope imported attachment references by task id and preserve assistant-ui reload `StartRunConfig`.
3. ISSUE-12 and ISSUE-15: fix invalid tab markup and keyboard-only command-palette dismissal.
4. ISSUE-11 and ISSUE-14: stop editor reconfiguration churn and protect in-progress outline edits.
5. ISSUE-18 and ISSUE-16: remove stale cross-task placeholder data from workspace/draft surfaces.
6. ISSUE-19: clamp and normalize localStorage panel sizes before passing to `defaultLayout`.
7. ISSUE-21: add `.min(1)` to the workspace title schema.

---

## ISSUE-01 · Major · Missing `onCancel` adapter in `useExternalStoreRuntime`

**File:** `apps/web/src/shell/assistant/useDocAgentAssistantRuntime.ts`

**Problem:**
`useExternalStoreRuntime` accepts an `onCancel?: () => Promise<void>` field in its adapter, which the runtime calls when the thread needs to cancel an in-progress run (e.g., via `aui.thread().cancelRun()`, component unmount while running, or future internal runtime triggers). This field is **not wired** — the adapter passes no `onCancel`.

The actual cancellation path is a plain DOM button in `DocAgentComposer` that calls `props.onCancel?.()` → `cancelActiveSession()` in `ConversationPane` → `api.cancelSession()`. This path completely bypasses the runtime's cancel mechanism. The runtime therefore has no way to self-cancel.

**Consequence:** If assistant-ui internally calls the cancel path (now or in a future version), nothing happens. `isRunning` stays `true` until the next timeline poll/refresh. Any future use of `aui.thread().cancelRun()` from within the component tree is silently a no-op.

**Reference:** `ExternalStoreAdapterBase.onCancel` in `@assistant-ui/core/dist/runtimes/external-store/external-store-adapter.d.ts`.

---

## ISSUE-02 · Major · Race condition in `importedAttachmentReferencesRef` across task switches

**File:** `apps/web/src/shell/assistant/useDocAgentAssistantRuntime.ts`

**Problem:**
```typescript
useEffect(() => {
  importedAttachmentReferencesRef.current = [];
}, [activeTaskId]);
```

When `activeTaskId` changes, the ref is cleared synchronously. However, if an `api.importTextInput()` call is already in flight (inside `attachmentAdapter.send()`), the `onImported` callback fires **after** the reset with a reference belonging to the old task. That reference is then pushed into `importedAttachmentReferencesRef.current` of the **new task**, and will be included in the next message sent to the new task.

**Consequence:** A file imported under task A can silently appear as an attachment in the first message sent to task B if the task is switched during the import upload.

**Reference:** `docAgentAttachmentAdapter.ts:send()` and `useDocAgentAssistantRuntime.ts` `onImported` callback.

---

## ISSUE-03 · Major · `onReload` signature drops `StartRunConfig` parameter

**File:** `apps/web/src/shell/assistant/useDocAgentAssistantRuntime.ts`

**Problem:**
The `ExternalStoreAdapter.onReload` type is:
```typescript
onReload?: (parentId: string | null, config: StartRunConfig) => Promise<void>
```

The implementation only accepts `parentId`:
```typescript
onReload: async (parentId: string | null) => {
  await onReloadInput?.(parentId);
},
```

TypeScript permits this (extra arguments are ignored), but the `StartRunConfig` object (which may carry `custom` metadata or future run configuration) is silently dropped and never forwarded to `onReloadInput` or `ConversationPane.reloadInput`.

**Consequence:** Any reload configuration provided by assistant-ui internals (model params, custom metadata) is lost. The signature will diverge from the runtime contract as the library evolves.

**Reference:** `ExternalStoreAdapterBase.onReload` in `external-store-adapter.d.ts`.

---

## ISSUE-04 · Minor · `unstable_capabilities` is an explicitly unstable API

**File:** `apps/web/src/shell/assistant/useDocAgentAssistantRuntime.ts`

**Problem:**
```typescript
unstable_capabilities: { copy: true },
```

The field is declared in the library types as:
```typescript
unstable_capabilities?: {
  copy?: boolean | undefined;
} | undefined;
```

The `unstable_` prefix is an explicit signal from the library authors that this field's shape, semantics, or existence may change without a major version bump. There is no currently documented stable alternative.

**Consequence:** Upgrading `@assistant-ui/react` could silently break the copy-to-clipboard action bar button without a type error, as the field might be renamed or removed.

**Reference:** `external-store-adapter.d.ts:ExternalStoreAdapterBase.unstable_capabilities`.

---

## ISSUE-05 · Retracted · `MessagePrimitive.Content` is exported and documented

**File:** `apps/web/src/shell/assistant/DocAgentThread.tsx`

**Original problem:**
The code uses `MessagePrimitive.Content` throughout:
```tsx
<MessagePrimitive.Content components={{ Text: TextPart, data: { by_name: { ... } } }} />
```

Inspection of `@assistant-ui/react/dist/primitives/message.d.ts` shows:
```typescript
export { MessagePrimitiveParts as Parts } from "./message/MessageParts.js";
export { MessagePrimitiveParts as Content } from "./message/MessageParts.js";  // alias
```

`Content` is an alias for `Parts` — same component, same props.

**Re-check result:**
Retracted as a finding. The local package explicitly exports both `Parts` and `Content`, and the assistant-ui MessagePrimitive API reference documents message primitive usage. This can be a style preference if the team wants a single canonical primitive name, but it is not currently evidence of an incorrect component lifecycle call.

---

## ISSUE-06 · Major · `threadStatusForEvent` silently maps unknown status values to `"complete"`

**File:** `apps/web/src/shell/assistant/docAgentAssistantMessages.ts`

**Problem:**
```typescript
function threadStatusForEvent(status: string): NonNullable<ThreadMessage["status"]> {
  if (status === "running" || status === "pending") return { type: "running" };
  if (status === "failed") return { type: "incomplete", reason: "error" };
  if (status === "cancelled") return { type: "incomplete", reason: "cancelled" };
  return { type: "complete", reason: "stop" };  // fallthrough for any unknown value
}
```

Any backend status string not in the explicit list (`"idle"`, `"queued"`, future statuses, typos) silently maps to `{ type: "complete", reason: "stop" }`. This means an event that is logically still pending or in an intermediate state will be rendered as successfully finished.

**Consequence:** If the backend adds a new status (e.g., `"queued"`, `"awaiting_resource"`) or an existing event arrives with `"idle"` status, it will appear complete in the UI. No error is surfaced.

---

## ISSUE-07 · Minor · Stale closure risk in `queuedCommand` effect due to suppressed exhaustive-deps lint rule

**File:** `apps/web/src/shell/panes/ConversationPane.tsx`

**Problem:**
```typescript
useEffect(() => {
  if (!queuedCommand || queuedCommandHandlingRef.current) return;
  queuedCommandHandlingRef.current = true;
  void submitOrCancel(queuedCommand).finally(() => {
    queuedCommandHandlingRef.current = false;
    onQueuedCommandHandled?.();
  });
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, [queuedCommand, onQueuedCommandHandled]);
```

`submitOrCancel` is omitted from the deps array via lint suppression. `submitOrCancel` is a `useCallback` that closes over `isRunning`, `activeSession`, `activeTask`, `ensureSession`, and other state. If any of these change between the moment `queuedCommand` is set and the moment it is processed, the stale version of `submitOrCancel` is used — silently executing with outdated session/task context.

**Consequence:** Edge case: if the active session changes in the same render cycle as a queued command being processed, the command is dispatched to the old session. Low probability in practice, but not impossible when navigating tasks rapidly.

---

## ISSUE-08 · Info · `DocAgentThreadContext` exists but `DataPart` bypasses it via prop drilling

**File:** `apps/web/src/shell/assistant/DocAgentThread.tsx`

**Problem:**
`DocAgentThreadContext` is created and provided at the `DocAgentThread` level with `activeSessionId`, `taskId`, `onApproved`, and `onOpenPath`. `AssistantMessage` correctly reads these from context. However, the `data.by_name` renderer map is an inline object that captures these values by closure and passes them as explicit props to `DataPart`:

```tsx
"docagent.tool-call": (part) => <DataPart {...part} activeSessionId={activeSessionId} taskId={taskId} onApproved={onApproved} onOpenPath={onOpenPath} />,
// ...repeated for all 5 data part types
```

`DataPart` then passes them to `DocAgentMessagePart` as props — it never reads `DocAgentThreadContext`.

**Consequence:** No functional bug today, but the context is redundant — it provides data that the data part renderers independently receive via closure. The duality means future maintainers may update one path and not the other. The 5-way prop repetition is also a maintenance surface.

---

## ISSUE-09 · Minor · `DocAgentComposer` cancel button bypasses runtime — `isRunning` state lag

**File:** `apps/web/src/shell/assistant/DocAgentComposer.tsx`, `apps/web/src/shell/panes/ConversationPane.tsx`

**Problem:**
When `isRunning=true`, the send button is replaced with a plain `<button>` that calls `props.onCancel?.()`. This routes to `cancelActiveSession` in `ConversationPane`, which calls `api.cancelSession()` then `refreshTimeline()` and `refreshSessions()`. The runtime itself never receives a cancel signal; it has no `onCancel` adapter (see ISSUE-01).

Between the cancel API call and the next timeline refresh completing, `isRunning` remains `true` in the runtime state. The stop button is still shown during this window. If the user clicks it again, a duplicate cancel request is issued.

**Consequence:** Duplicate cancel API calls on rapid double-click. The `refreshTimeline` call after cancel eventually corrects `isRunning`, but there is no debounce or guard against double-fire during the async refresh window.

---

## ISSUE-10 · Minor · `useTimeline` SSE `onerror` handler issues a redundant full-timeline fetch before reconnect

**File:** `apps/web/src/shell/state/useTimeline.ts`

**Problem:**
```typescript
source.onerror = () => {
  closeCurrentSource?.();
  if (cancelled) return;
  // Re-fetch timeline to catch up on missed events
  void api.getTimeline(currentSessionId).then(...)   // fetch #1
  // Reconnect with exponential backoff
  reconnectId = window.setTimeout(() => {
    if (!cancelled) connect();  // connect() → new EventSource → onmessage may trigger fetch #2
  }, backoffMs);
};
```

The `onmessage` handler also triggers a full `api.getTimeline()` fetch when it receives a `session_status` or `error` event. If the SSE disconnects mid-session-status event, both the `onerror` fetch and the reconnect's first successful `onmessage` fetch can fire in rapid succession, resulting in two redundant full-timeline fetches.

**Consequence:** Not a correctness issue (both fetches call `replaceWithIdDedup` and set the same data), but causes unnecessary backend load during reconnects, especially under poor network conditions with frequent SSE drops.

---

## ISSUE-11 · Major · `DraftEditor` — `selectionListener` extension recreated on every render, triggering full CodeMirror reconfiguration

**File:** `apps/web/src/shell/editor/DraftEditor.tsx`

**Problem:**
```typescript
// Inline in component body — no useMemo
const selectionListener = EditorView.updateListener.of((viewUpdate) => { ... });

<CodeMirror extensions={[markdown(), EditorView.lineWrapping, selectionListener]} ... />
```

`selectionListener` is created inline without memoization. Each render produces a new `EditorView.updateListener` instance, making the `extensions` prop a new array reference every render.

`@uiw/react-codemirror`'s `useCodeMirror` hook depends on `extensions` in a `useEffect`:
```javascript
useEffect(() => {
  view.dispatch({ effects: StateEffect.reconfigure.of(getExtensions) });
}, [theme, extensions, ...]); // confirmed in esm/useCodeMirror.js:148
```

`StateEffect.reconfigure` is a **full** CodeMirror extension reconfiguration. It fires on every parent re-render (including `saveState` cycling every 800ms, every timeline poll, and every local state update in `DraftTab`).

**Consequence:** The CodeMirror editor is fully reconfigured multiple times per minute. This can cause undo-history loss, selection/cursor reset, and visible jank. Correct fix: wrap `selectionListener` in `useMemo([])` and likewise `[markdown(), EditorView.lineWrapping]`.

**Reference:** `@uiw/react-codemirror/esm/useCodeMirror.js:141–148`.

---

## ISSUE-12 · Major · `EditorPane` — `<button>` nested inside `<TabsTrigger>` (which renders as `<button>`) is invalid HTML

**File:** `apps/web/src/shell/panes/EditorPane.tsx`

**Problem:**
```tsx
<TabsTrigger value={tab.id}>         {/* Radix renders this as <button> */}
  <span>{tab.title}</span>
  {tab.id !== "draft" && (
    <button type="button" onClick={(e) => { e.stopPropagation(); onCloseTab(tab.id); }}>
      <X size={12} />
    </button>
  )}
</TabsTrigger>
```

`@radix-ui/react-tabs` `Trigger` renders as a `<button>` element by default. The HTML spec forbids interactive content (including `<button>`) inside `<button>`. Browsers silently repair the DOM by ejecting the inner button, which breaks React's synthetic event model: `e.stopPropagation()` may not prevent tab selection, the close button may become unreachable via keyboard, and screen readers report a malformed tab widget.

**Consequence:** Closing a tab in some browsers triggers a tab switch simultaneously. Keyboard users cannot Tab-focus the close button independently. Accessibility tree is broken.

**Fix direction:** Use `asChild` to render `TabsTrigger` as a `<div>`, or place the close button as an absolutely-positioned sibling rendered outside the trigger element.

---

## ISSUE-13 · Minor · `WorkspacePane` — `react-arborist` `Tree` has hardcoded `height={680}`, ignoring panel resize

**File:** `apps/web/src/shell/panes/WorkspacePane.tsx`

**Problem:**
```tsx
<Tree data={nodes} height={680} rowHeight={30} width="100%" ...>
```

`react-arborist` uses `react-window` for virtualization; the `height` prop sets the virtual list viewport. When provided as a literal number, the list is fixed to that pixel height regardless of the actual panel size.

The left panel is resizable (via `react-resizable-panels`) but the tree does not respond to panel resize events because the virtual list viewport is hardcoded. On laptop screens at common resolutions the 680px list overflows the workspace panel; on large monitors it leaves significant blank space.

**Consequence:** The tree is either clipped or over-spaced depending on viewport size, and never adapts to panel resizing.

**Re-check correction:** The original note that omitting `height` makes react-arborist measure the container automatically is not supported by the installed package. Its `TreeProps` type has `height?: number`, and the local `TreeApi.height` getter falls back to `500` when no height is provided. Correct fix direction: measure the available container height with `ResizeObserver` or an equivalent hook and pass the measured number to `Tree`.

---

## ISSUE-14 · Major · `OutlineCard` — user edits to the outline textarea are silently overwritten when the event refreshes

**File:** `apps/web/src/shell/conversation/cards/OutlineCard.tsx`

**Problem:**
```typescript
useEffect(() => {
  if (!taskId) return;
  api.getWorkspaceFile(taskId, outlinePath)
    .then((file) => { if (!cancelled) setOutline(file.content); })  // overwrites user edits
    .catch(() => { if (!cancelled) setOutline(event.summary); });
}, [event.summary, outlinePath, taskId]);
```

`event.summary` is listed as a dependency but is not used in the effect body (only in the `.catch()` fallback). Its presence means the effect re-runs and re-fetches the outline file whenever the event's summary text changes — which happens when the backend transitions the event's status from `"running"` to `"succeeded"` and updates its summary.

There is no dirty-state guard. The fetched file content unconditionally replaces `outline` state, discarding any user edits made since the component mounted.

**Consequence:** A user editing the outline textarea (common UX: review and adjust before approving) loses their changes the next time the SSE stream delivers an event update or `refreshTimeline()` is called. The approve button then submits the server's content rather than the user's revision.

---

## ISSUE-15 · Minor · `CommandPalette` — no Escape key handler; palette cannot be closed by keyboard

**File:** `apps/web/src/shell/CommandPalette.tsx`, `apps/web/src/shell/AppShell.tsx`

**Problem:**
The command palette opens on `Ctrl+Shift+P` but has no keyboard close path:

```typescript
// AppShell.tsx — only opens, no Escape branch
function handleKeyDown(event: React.KeyboardEvent) {
  if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === "p") {
    setCommandOpen(true);
  }
}

// CommandPalette.tsx — dismiss only via mouse click on overlay
<div className="command-overlay" onMouseDown={onClose}>
  <Command onMouseDown={(e) => e.stopPropagation()}>...</Command>
</div>
```

`cmdk` v1 does not handle `Escape` internally (confirmed: the string "Escape" does not appear in `cmdk/dist/index.mjs`). The palette can only be dismissed by clicking outside it.

**Consequence:** Keyboard-only users have no way to close the command palette. This violates WCAG 2.1 SC 2.1.2 (No Keyboard Trap) and contradicts the UX convention of every command palette implementation (VS Code, Linear, GitHub).

---

## ISSUE-16 · Minor · `useDraft` + `keepPreviousData` can show stale draft after task switch

**File:** `apps/web/src/shell/state/useDraft.ts`, `apps/web/src/shell/AppShell.tsx`, `apps/web/src/shell/editor/useAutoSave.ts`

**Problem:**
`useDraft` opts into `keepPreviousData`:
```typescript
useQuery({ queryKey: ["draft", taskId], ..., placeholderData: keepPreviousData })
```

When `activeTaskId` changes, `draftQuery.isSuccess` can stay `true` and `draftQuery.data` still holds the old task's draft until the new fetch completes.

`draftAutoSaveEnabled` is derived as:
```typescript
const draftTaskId = draftQuery.isSuccess ? (workspaces.activeTask?.id ?? null) : null;
const draftAutoSaveEnabled = draftTaskId === (workspaces.activeTask?.id ?? null) && !activeSessionIsRunning;
```

Both sides of the equality use `workspaces.activeTask?.id`, so `draftAutoSaveEnabled=true` immediately after the task switch, while `draft` content may still be the old task's stale markdown. Inside `useAutoSave`, the first effect resets `lastSaved.current` to that stale content.

Existing test coverage includes a regression test that prevents the old task's draft from being auto-saved into the newly selected task while the new draft is loading. That means the strongest original claim is currently guarded by test coverage.

**Consequence:** The remaining issue is stale UI: the editor can briefly show the previous task's draft under the newly selected task until the new query resolves. If the user edits during that window, behavior depends on timing and autosave state. Prefer tracking the task id associated with the loaded draft, or avoid `keepPreviousData` for the editable draft surface.

---

## ISSUE-17 · Info · `SettingsDrawer` — `modal={false}` suppresses overlay at runtime but `SheetContent` hardcodes `<SheetOverlay>` unconditionally

**File:** `apps/web/src/components/ui/sheet.tsx`, `apps/web/src/shell/SettingsDrawer.tsx`

**Problem:**
`SheetContent` always renders `<SheetOverlay />` (styled with `bg-black/80`):
```tsx
const SheetContent = forwardRef(({ side, className, children, ...props }, ref) => (
  <SheetPortal>
    <SheetOverlay />            {/* always present in JSX */}
    <SheetPrimitive.Content ...>
```

However, Radix Dialog suppresses the overlay when `modal={false}`:
```javascript
// @radix-ui/react-dialog source (line 148)
return context.modal ? <DialogOverlayImpl ... /> : null;
```

So `<SheetOverlay />` renders nothing at runtime when `Sheet modal={false}` is set in `SettingsDrawer`. The behavior is correct today, but the relationship is invisible at the call site.

**Consequence:** If the `modal={false}` prop is ever removed or forgotten (e.g., when copying the sheet pattern for a new modal use case), the dark full-screen overlay appears and blocks the entire app behind the drawer. There is no indication in `sheet.tsx` that the overlay depends on `modal={false}` to be suppressed.

---

## ISSUE-18 · Major · `useWorkspaceTree` + `keepPreviousData` can attach stale files to the newly selected task

**File:** `apps/web/src/shell/state/useWorkspaceTree.ts`, `apps/web/src/shell/AppShell.tsx`

**Problem:**
`useWorkspaceTree` opts into placeholder data:
```typescript
useQuery({
  queryKey: ["workspace", taskId],
  queryFn: () => api.getWorkspace(taskId!),
  enabled: !!taskId,
  staleTime: 10_000,
  placeholderData: keepPreviousData,
});
```

When the active task changes, TanStack Query can expose the previous task's workspace tree while the new task's workspace request is still loading. `AppShell` then builds tree data by indexing the current `activeTask.id` to `workspaceTreeQuery.data`:
```typescript
workspaces.activeTask && workspaceTreeQuery.data
  ? { [workspaces.activeTask.id]: workspaceTreeQuery.data }
  : {}
```

That means old workspace files can be displayed as if they belonged to the newly selected task.

**Consequence:** During the loading window after a task switch, the left tree can show stale files. If the user clicks one, `openWorkspaceFile()` uses the new active task id with an old file path. Best case: the API returns not found. Worst case: the same relative path exists in both workspaces and the UI opens a file the user did not intend.

**Reference:** TanStack Query v5 `placeholderData: keepPreviousData` keeps previous query data visible while a query key changes.

---

## ISSUE-19 · Minor · Persisted resizable layout is not validated before being used as `defaultLayout`

**File:** `apps/web/src/shell/state/useCollapse.ts`, `apps/web/src/shell/AppShell.tsx`

**Problem:**
`readNumber()` accepts any finite positive number from localStorage:
```typescript
return Number.isFinite(value) && value > 0 ? value : fallback;
```

`AppShell` uses those values directly to compute the center panel:
```typescript
defaultLayout={{
  left: collapse.leftPanelSize,
  center: 100 - collapse.leftPanelSize - collapse.rightPanelSize,
  right: collapse.rightPanelSize,
}}
```

If localStorage contains `leftPanelSize=80` and `rightPanelSize=80`, `center` becomes `-60`. The installed `react-resizable-panels` types document `defaultLayout` as a map of panel id to percentages in the `0..100` range.

**Consequence:** Corrupt or stale localStorage can produce an invalid default layout on app startup. The panel library may clamp it, but the app should not hand invalid layout data to the component. Clamp the individual values and normalize the total before passing `defaultLayout`.

---

## ISSUE-20 · Info · Collapsed panel state is stored but never connected to `react-resizable-panels`

**File:** `apps/web/src/shell/state/useCollapse.ts`, `apps/web/src/shell/AppShell.tsx`

**Problem:**
`useCollapse` stores `leftCollapsed`, `rightCollapsed`, and exposes setters that persist those values. `AppShell` renders collapsible panels:
```tsx
<ResizablePanel id="left" ... collapsedSize={4} collapsible>
...
<ResizablePanel id="right" ... collapsedSize={4} collapsible>
```

However, no `panelRef` is passed, no `collapse()` / `expand()` calls are made, and no UI uses `setLeftCollapsed` or `setRightCollapsed`. The persisted collapsed values are not read when rendering the panels.

**Consequence:** The collapse state is dead state. It can mislead future maintainers into thinking panel collapse/restore is implemented when only size persistence is active. Either wire the state to the panel imperative API or remove it until collapse controls exist.

---

## ISSUE-21 · Minor · `WorkspacePane` — zod `title` field has no `.min(1)`, allowing empty workspace titles

**File:** `apps/web/src/shell/panes/WorkspacePane.tsx`

**Problem:**
```typescript
const createWorkspaceSchema = z.object({
  title: z.string(),                              // no minimum — empty string passes
  description: z.string().min(1, "Description is required"),
});
```

`description` is validated with `.min(1)`, but `title` uses bare `z.string()` which accepts `""`. React Hook Form with `zodResolver` will pass an empty title through to `onCreateWorkspace`, which calls `api.createTask(docTypeId, { title: "", description })`. The task is created with `title: ""`.

In `buildWorkspaceTreeData`, the workspace tree label is:
```typescript
name: task.title ?? task.brief,
```

`?? ` is nullish coalescing — `""` is falsy but not null/undefined, so it is used directly. The workspace node appears with an empty label in the tree.

**Consequence:** A user who submits the form with a blank title receives no validation error, creates a workspace with no visible name in the tree, and cannot rename it after creation. The `description` field correctly blocks empty input but `title` does not, creating inconsistent UX.

---
