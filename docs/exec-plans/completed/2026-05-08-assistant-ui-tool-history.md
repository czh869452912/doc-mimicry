# Assistant-UI Tool History Implementation Plan

> **Archive note (2026-05-17):** This completed plan preserves its original
> execution checklist for historical traceability. Any unchecked boxes below are
> not active work; use active plan/review directories for current tasks.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade DocAgent semantic timeline rows from compact event pills into explicit assistant-ui tool-history data parts while preserving the current outline/checklist/artifact/approval cards.

**Architecture:** Keep the existing `useExternalStoreRuntime` bridge and `ThreadMessage[]` mapping. Introduce a focused tool-history data model in `docAgentAssistantMessages.ts`, render it through `DocAgentMessageParts.tsx`, and style it in `assistant-ui.css`. Do not add backend APIs in this pass; derive tool history from existing `TimelineEvent.kind`, `summary`, `paths`, and `status`.

**Tech Stack:** React 19, TypeScript, `@assistant-ui/react` custom data parts, Vitest, Playwright.

---

## Scope

- Replace generic `docagent.event-pill` data parts with `docagent.tool-call` data parts for semantic agent work events.
- Preserve existing card data parts:
  - `docagent.outline-card`
  - `docagent.checklist-card`
  - `docagent.artifact-card`
  - `docagent.approval-card`
- Keep current backend timeline contract unchanged.
- Keep Markdown as the internal document format.
- Keep current copy actions and assistant-ui thread/composer primitives.

## Non-Goals

- Do not implement retry/reload.
- Do not implement BranchPicker.
- Do not implement attachments.
- Do not implement dictation.
- Do not replace the editor selection bar with assistant-ui `SelectionToolbar`.
- Do not create a new backend tool-call schema in this pass.

## Files

- Modify: `apps/web/src/shell/assistant/docAgentAssistantMessages.ts`
  - Define tool-call data types.
  - Map timeline event kinds to stable tool labels, categories, path summaries, and display status.
  - Emit `docagent.tool-call` data parts for non-card semantic events.
- Modify: `apps/web/src/shell/assistant/DocAgentMessageParts.tsx`
  - Render tool-call data parts with explicit tool name, status, summary, and paths.
  - Keep card rendering untouched.
- Modify: `apps/web/src/shell/assistant/DocAgentThread.tsx`
  - Register `docagent.tool-call` in the assistant-ui data part renderer.
  - Remove `docagent.event-pill` renderer after migration.
- Modify: `apps/web/src/shell/theme/assistant-ui.css`
  - Add compact tool-history row styles.
  - Keep layout dimensions stable and readable in the center pane.
- Modify: `apps/web/src/shell/assistant/__tests__/docAgentAssistantMessages.test.ts`
  - Cover tool-call data mapping.
  - Cover failed/running/succeeded statuses.
  - Cover path summaries.
- Modify: `apps/web/src/shell/assistant/__tests__/DocAgentMessageParts.test.tsx`
  - Cover rendered tool-call labels, status, summary, and paths.
- Modify: `apps/web/tests/core-loop.spec.ts`
  - Verify visible tool history in the core loop.
- Modify: `docs/reviews/completed/2026-05-07-project-review-assistant-ui-integration.md`
  - Record that deeper tool-call history is now covered at the current timeline-contract level.

---

## Task 1: Tool-Call Data Model And Mapping

**Files:**
- Modify: `apps/web/src/shell/assistant/docAgentAssistantMessages.ts`
- Test: `apps/web/src/shell/assistant/__tests__/docAgentAssistantMessages.test.ts`

- [x] **Step 1: Write failing mapping tests**

Add tests that expect a semantic event to map to `docagent.tool-call`:

```ts
it("maps semantic work events to assistant-ui tool-call data parts", () => {
  const messages = mapTimelineEventsToAssistantMessages([
    event({
      id: "evt-context",
      kind: "build_context",
      summary: "Built context files",
      paths: ["context/user_intent.md", "context/doc_map.md"],
    }),
  ]);

  expect(messages[0]).toMatchObject({
    id: "evt-context",
    role: "assistant",
    content: [
      {
        type: "data",
        name: "docagent.tool-call",
        data: {
          kind: "tool-call",
          toolName: "build_context",
          title: "Build context",
          category: "edit",
          status: "succeeded",
          summary: "Built context files",
          paths: ["context/user_intent.md", "context/doc_map.md"],
          pathSummary: "context/user_intent.md, context/doc_map.md",
        },
      },
    ],
    metadata: { custom: { timelineEventId: "evt-context", timelineKind: "build_context" } },
  });
});
```

Add a status coverage test:

```ts
it("normalizes tool-call display status from timeline status", () => {
  const messages = mapTimelineEventsToAssistantMessages([
    event({ id: "evt-failed", kind: "update_draft", summary: "Draft failed", status: "failed" }),
    event({ id: "evt-running", kind: "generate_outline", summary: "Generating", status: "running" }),
  ]);

  expect(messages.map((message) => message.content[0])).toMatchObject([
    { type: "data", name: "docagent.tool-call", data: { status: "failed" } },
    { type: "data", name: "docagent.tool-call", data: { status: "running" } },
  ]);
});
```

- [x] **Step 2: Run mapping tests and verify failure**

Run:

```powershell
cd apps\web
npm run test:unit -- src/shell/assistant/__tests__/docAgentAssistantMessages.test.ts
```

Expected: FAIL because mapper still emits `docagent.event-pill`.

- [x] **Step 3: Implement the tool-call data model**

In `docAgentAssistantMessages.ts`, replace `PillCategory` and the event-pill variant with:

```ts
export type ToolCallCategory = "read" | "search" | "write" | "review" | "export" | "system";
export type ToolCallDisplayStatus = "running" | "succeeded" | "failed" | "cancelled";

export interface DocAgentToolCallData {
  kind: "tool-call";
  category: ToolCallCategory;
  event: TimelineEvent;
  pathSummary?: string;
  paths: string[];
  status: ToolCallDisplayStatus;
  summary: string;
  title: string;
  toolName: string;
}
```

Update `DocAgentAssistantData`:

```ts
export type DocAgentAssistantData =
  | DocAgentToolCallData
  | { kind: "outline-card"; event: TimelineEvent }
  | { kind: "checklist-card"; event: TimelineEvent }
  | { kind: "artifact-card"; event: TimelineEvent }
  | { kind: "approval-card"; event: TimelineEvent };
```

Update `AssistantDataName` to include `docagent.tool-call` and remove `docagent.event-pill`:

```ts
type AssistantDataName =
  | "docagent.tool-call"
  | "docagent.outline-card"
  | "docagent.checklist-card"
  | "docagent.artifact-card"
  | "docagent.approval-card";
```

Replace the fallback return in `dataPartForEvent`:

```ts
return {
  name: "docagent.tool-call",
  data: toolCallDataForEvent(event),
};
```

Add helpers:

```ts
function toolCallDataForEvent(event: TimelineEvent): DocAgentToolCallData {
  return {
    kind: "tool-call",
    category: categoryForKind(event.kind),
    event,
    paths: event.paths,
    pathSummary: event.paths.length > 0 ? event.paths.join(", ") : undefined,
    status: statusForEvent(event.status),
    summary: event.summary || event.kind,
    title: titleForKind(event.kind),
    toolName: event.kind,
  };
}

function titleForKind(kind: string): string {
  const titles: Record<string, string> = {
    read_skill: "Read document skill",
    analyze_examples: "Analyze examples",
    build_context: "Build context",
    extract_style: "Extract style notes",
    extract_structure: "Extract structure notes",
    generate_outline: "Generate outline",
    update_draft: "Update draft",
    revise_selection: "Revise selection",
    create_checkpoint: "Create checkpoint",
    run_checklist: "Run checklist",
    export_markdown: "Export Markdown",
    export_docx: "Export DOCX",
    export_pdf: "Export PDF",
    convert_input: "Convert input",
  };
  return titles[kind] ?? kind.replaceAll("_", " ");
}

function statusForEvent(status: string): ToolCallDisplayStatus {
  if (status === "failed") return "failed";
  if (status === "cancelled") return "cancelled";
  if (status === "running" || status === "pending") return "running";
  return "succeeded";
}
```

Update `categoryForKind`:

```ts
function categoryForKind(kind: string): ToolCallCategory {
  if (kind === "read_skill" || kind === "convert_input") return "read";
  if (kind === "analyze_examples") return "search";
  if (kind === "run_checklist") return "review";
  if (kind === "export_markdown" || kind === "export_docx" || kind === "export_pdf") return "export";
  if (
    kind === "build_context" ||
    kind === "extract_style" ||
    kind === "extract_structure" ||
    kind === "generate_outline" ||
    kind === "propose_outline" ||
    kind === "update_draft" ||
    kind === "revise_selection" ||
    kind === "create_checkpoint"
  ) {
    return "write";
  }
  return "system";
}
```

- [x] **Step 4: Run mapping tests and verify pass**

Run:

```powershell
cd apps\web
npm run test:unit -- src/shell/assistant/__tests__/docAgentAssistantMessages.test.ts
```

Expected: PASS.

---

## Task 2: Tool-Call Renderer

**Files:**
- Modify: `apps/web/src/shell/assistant/DocAgentMessageParts.tsx`
- Modify: `apps/web/src/shell/assistant/DocAgentThread.tsx`
- Test: `apps/web/src/shell/assistant/__tests__/DocAgentMessageParts.test.tsx`

- [x] **Step 1: Write failing renderer test**

Replace the event-pill test with:

```ts
it("renders tool-call data parts", () => {
  const { container } = renderPart({
    kind: "tool-call",
    category: "write",
    toolName: "build_context",
    title: "Build context",
    status: "succeeded",
    summary: "Built context",
    paths: ["context/brief.md"],
    pathSummary: "context/brief.md",
    event: event({ id: "evt-context", kind: "build_context", summary: "Built context" }),
  });

  expect(container.querySelector(".aui-tool-call")).toBeTruthy();
  expect(screen.getByText("Build context")).toBeTruthy();
  expect(screen.getByText("succeeded")).toBeTruthy();
  expect(screen.getByText("Built context")).toBeTruthy();
  expect(screen.getByText("context/brief.md")).toBeTruthy();
});
```

- [x] **Step 2: Run renderer test and verify failure**

Run:

```powershell
cd apps\web
npm run test:unit -- src/shell/assistant/__tests__/DocAgentMessageParts.test.tsx
```

Expected: FAIL because `tool-call` is not rendered yet.

- [x] **Step 3: Implement tool-call rendering**

In `DocAgentMessageParts.tsx`, replace the `event-pill` branch with:

```tsx
if (data.kind === "tool-call") {
  return (
    <div className="aui-timeline-part aui-timeline-part--tool">
      <article className="aui-tool-call" data-category={data.category} data-status={data.status}>
        <header className="aui-tool-call__header">
          <span className="aui-tool-call__name">{data.title}</span>
          <span className="aui-tool-call__status">{data.status}</span>
        </header>
        <p className="aui-tool-call__summary">{data.summary}</p>
        {data.pathSummary && <small className="aui-tool-call__paths">{data.pathSummary}</small>}
      </article>
    </div>
  );
}
```

In `DocAgentThread.tsx`, change the data renderer registration from:

```tsx
"docagent.event-pill": (part) => <DataPart {...part} {...props} />,
```

to:

```tsx
"docagent.tool-call": (part) => <DataPart {...part} {...props} />,
```

- [x] **Step 4: Run renderer and mapping tests**

Run:

```powershell
cd apps\web
npm run test:unit -- src/shell/assistant/__tests__/DocAgentMessageParts.test.tsx src/shell/assistant/__tests__/docAgentAssistantMessages.test.ts
```

Expected: PASS.

---

## Task 3: Tool-Call Styling

**Files:**
- Modify: `apps/web/src/shell/theme/assistant-ui.css`
- Test: `apps/web/tests/core-loop.spec.ts`

- [x] **Step 1: Add E2E expectation for visible tool history**

In `apps/web/tests/core-loop.spec.ts`, extend `start loop produces outline card` after the outline assertion:

```ts
await expect(page.locator(".aui-tool-call").filter({ hasText: "Read document skill" })).toBeVisible();
await expect(page.locator(".aui-tool-call").filter({ hasText: "Analyze examples" })).toBeVisible();
await expect(page.locator(".aui-tool-call").filter({ hasText: "Build context" })).toBeVisible();
```

- [x] **Step 2: Run the targeted E2E and verify failure if styling/renderer is incomplete**

Run:

```powershell
cd apps\web
npx playwright test tests/core-loop.spec.ts -g "start loop produces outline card"
```

Expected: PASS if Task 2 renderer is complete; FAIL if `.aui-tool-call` is missing.

- [x] **Step 3: Add compact tool-call styles**

In `assistant-ui.css`, remove `.aui-event-pill-row` rules after the renderer migration. Add:

```css
.aui-timeline-part--tool {
  display: grid;
}

.aui-tool-call {
  display: grid;
  gap: 4px;
  max-width: 560px;
  padding: 7px 9px;
  color: var(--color-body);
  background: var(--color-canvas-soft);
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-md);
  font-size: 12px;
}

.aui-tool-call__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
}

.aui-tool-call__name {
  min-width: 0;
  overflow: hidden;
  color: var(--color-ink);
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.aui-tool-call__status {
  flex: 0 0 auto;
  color: var(--color-muted);
  font-size: 11px;
}

.aui-tool-call__summary {
  margin: 0;
  color: var(--color-body);
}

.aui-tool-call__paths {
  min-width: 0;
  overflow: hidden;
  color: var(--color-muted);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.aui-tool-call[data-status="failed"] {
  border-color: rgb(176 57 57 / 36%);
}

.aui-tool-call[data-status="running"] .aui-tool-call__status {
  color: var(--color-accent);
}
```

- [x] **Step 4: Run targeted E2E**

Run:

```powershell
cd apps\web
npx playwright test tests/core-loop.spec.ts -g "start loop produces outline card"
```

Expected: PASS.

---

## Task 4: Review Doc And Full Verification

**Files:**
- Modify: `docs/reviews/completed/2026-05-07-project-review-assistant-ui-integration.md`

- [x] **Step 1: Update review status**

In the follow-up resolved list, add:

```md
- **Assistant-ui tool history formalized.** Semantic timeline work events now render as explicit `docagent.tool-call` assistant-ui data parts with tool names, statuses, summaries, and workspace paths. This covers deeper tool-call history at the current timeline-contract level without requiring a backend schema migration.
```

In the still-open assistant-ui advanced capabilities bullet, remove “deeper tool-call history beyond the current semantic event cards” and keep:

```md
- Assistant-ui advanced capabilities that require additional product/backend semantics: BranchPicker, retry/reload semantics, attachments, dictation, and assistant-ui `SelectionToolbar` replacement for the editor selection bar.
```

- [x] **Step 2: Run full verification**

Run:

```powershell
cd apps\web
npm run test:unit
npm run build
npm run test:e2e
cd ..\..
.local\dev\.venv\Scripts\python.exe -m pytest -q
```

Expected:

- Web unit tests pass.
- Build passes. Existing Vite circular chunk warnings are acceptable unless they become errors.
- Playwright E2E passes.
- Backend pytest passes.

- [ ] **Step 3: Commit**

Run:

```powershell
git add apps/web/src/shell/assistant/docAgentAssistantMessages.ts apps/web/src/shell/assistant/DocAgentMessageParts.tsx apps/web/src/shell/assistant/DocAgentThread.tsx apps/web/src/shell/theme/assistant-ui.css apps/web/src/shell/assistant/__tests__/docAgentAssistantMessages.test.ts apps/web/src/shell/assistant/__tests__/DocAgentMessageParts.test.tsx apps/web/tests/core-loop.spec.ts docs/reviews/completed/2026-05-07-project-review-assistant-ui-integration.md docs/exec-plans/completed/2026-05-08-assistant-ui-tool-history.md
git commit -m "Formalize assistant tool history"
```

Expected: one focused commit.

---

## Acceptance Criteria

- Timeline semantic work events render as `.aui-tool-call`.
- Tool-call rows show:
  - user-readable tool title
  - normalized status
  - summary
  - path summary when paths exist
- Existing outline/checklist/artifact/approval cards still render as cards.
- Existing copy action remains available on assistant messages.
- `npm run test:unit`, `npm run build`, `npm run test:e2e`, and backend pytest all pass.

## Rollback Notes

- If the tool-call renderer causes unexpected assistant-ui data-part rendering issues, revert `DocAgentThread.tsx` to the previous `docagent.event-pill` registration and keep the mapping tests failing until the data-part shape is corrected.
- If E2E becomes brittle due to timeline ordering, assert the presence of tool-call rows by text rather than strict order.
- Do not remove card data parts during rollback; cards are independent of this tool-history migration.
