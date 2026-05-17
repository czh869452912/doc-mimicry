# Frontend Polish Implementation Plan

> **Archive note (2026-05-17):** This completed plan preserves its original
> execution checklist for historical traceability. Any unchecked boxes below are
> not active work; use active plan/review directories for current tasks.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix four frontend issues from the 2026-05-07 review: remove spurious `Content-Type` headers from GET requests, add React Error Boundaries around each pane, replace the primitive diff viewer with `react-diff-viewer-continued`, and add `react-hook-form` + `zod` validation to the workspace creation form.

**Architecture:** All changes are within `apps/web/`. No new routing, no state management changes, no component restructuring beyond what each task requires.

**Tech Stack:** React 19, TypeScript, Vitest + @testing-library/react, react-diff-viewer-continued, react-hook-form, zod, @hookform/resolvers

---

## File Map

**Modify:**
- `apps/web/src/api.ts` — conditionally include Content-Type header (I5)
- `apps/web/src/shell/AppShell.tsx` — wrap panes in ErrorBoundary (M3)

**Create:**
- `apps/web/src/shell/ErrorBoundary.tsx` — reusable React error boundary (M3)
- `apps/web/src/shell/__tests__/ErrorBoundary.test.tsx` — component test

**Modify:**
- `apps/web/src/shell/editor/DiffViewer.tsx` — rewrite using react-diff-viewer-continued (I6)
- `apps/web/src/shell/editor/tabs/DiffTab.tsx` — update props if needed

**Modify:**
- `apps/web/src/shell/panes/WorkspacePane.tsx` — replace native form with react-hook-form + zod (I7)

---

## Task 1: Fix Content-Type header on GET requests (I5)

**Files:**
- Modify: `apps/web/src/api.ts`

Currently every `fetch` call attaches `Content-Type: application/json` even on GET requests that have no body. Some proxies and caches treat this as a protocol violation.

- [ ] **Step 1: Write failing test**

Create `apps/web/src/shell/__tests__/api.test.ts`:

```typescript
import { describe, expect, it, vi, beforeEach } from "vitest";

// We test the underlying fetch call headers, not the api wrapper functions,
// since fetch is globally available in jsdom.
describe("api request helper", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    }));
  });

  it("does not include Content-Type on GET requests", async () => {
    // Import api after stubbing fetch so the stub is active
    const { api } = await import("../../api");
    await api.listTasks();

    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit];
    const headers = init?.headers as Record<string, string> | undefined;
    expect(headers?.["Content-Type"]).toBeUndefined();
  });

  it("includes Content-Type on POST requests with body", async () => {
    const { api } = await import("../../api");
    await api.createTask("prd", "Build a search feature");

    const [, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit];
    const headers = init?.headers as Record<string, string>;
    expect(headers?.["Content-Type"]).toBe("application/json");
  });
});
```

- [ ] **Step 2: Run to confirm it fails**

```bash
cd apps/web && npx vitest run src/shell/__tests__/api.test.ts
```

Expected: first test fails — Content-Type IS present on GET requests.

- [ ] **Step 3: Fix api.ts**

In `apps/web/src/api.ts`, update the `request` function:

```typescript
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const contentTypeHeader = init?.body !== undefined
    ? { "Content-Type": "application/json" }
    : {};
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { ...contentTypeHeader, ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    let detail = "";
    try {
      const body = (await response.json()) as { detail?: unknown };
      detail = typeof body.detail === "string" ? `: ${body.detail}` : "";
    } catch {
      detail = "";
    }
    throw new Error(`${response.status} ${response.statusText}${detail}`);
  }
  return response.json() as Promise<T>;
}
```

- [ ] **Step 4: Run tests**

```bash
npx vitest run src/shell/__tests__/api.test.ts
```

Expected: both tests pass.

- [ ] **Step 5: Run full web test suite**

```bash
npx vitest run
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/api.ts apps/web/src/shell/__tests__/api.test.ts
git commit -m "Only send Content-Type header when request has a body (I5)"
```

---

## Task 2: Add React Error Boundaries (M3)

**Files:**
- Create: `apps/web/src/shell/ErrorBoundary.tsx`
- Create: `apps/web/src/shell/__tests__/ErrorBoundary.test.tsx`
- Modify: `apps/web/src/shell/AppShell.tsx`

Without error boundaries, any unhandled render error in a pane white-screens the entire application. Each pane should fail independently.

- [ ] **Step 1: Write failing test**

Create `apps/web/src/shell/__tests__/ErrorBoundary.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ErrorBoundary } from "../ErrorBoundary";

function Bomb(): never {
  throw new Error("boom");
}

describe("ErrorBoundary", () => {
  it("renders fallback when child throws", () => {
    // Suppress React's error boundary console.error noise in the test output
    const spy = vi.spyOn(console, "error").mockImplementation(() => undefined);

    render(
      <ErrorBoundary label="Test pane">
        <Bomb />
      </ErrorBoundary>
    );

    expect(screen.getByText(/Test pane/)).toBeTruthy();
    expect(screen.getByText(/something went wrong/i)).toBeTruthy();
    spy.mockRestore();
  });

  it("renders children when no error", () => {
    render(
      <ErrorBoundary label="Test pane">
        <p>content</p>
      </ErrorBoundary>
    );

    expect(screen.getByText("content")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run to confirm it fails**

```bash
npx vitest run src/shell/__tests__/ErrorBoundary.test.tsx
```

Expected: FAIL — `ErrorBoundary` does not exist yet.

- [ ] **Step 3: Create ErrorBoundary.tsx**

Create `apps/web/src/shell/ErrorBoundary.tsx`:

```tsx
import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  label: string;
}

interface State {
  hasError: boolean;
  message: string;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, message: "" };

  static getDerivedStateFromError(error: unknown): State {
    const message = error instanceof Error ? error.message : String(error);
    return { hasError: true, message };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error(`[${this.props.label}] unhandled render error`, error, info);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="pane-error" role="alert">
          <p className="pane-note pane-note--error">
            <strong>{this.props.label}</strong> — Something went wrong.
          </p>
          <p className="pane-note body-sm">{this.state.message}</p>
        </div>
      );
    }
    return this.props.children;
  }
}
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
npx vitest run src/shell/__tests__/ErrorBoundary.test.tsx
```

Expected: both tests pass.

- [ ] **Step 5: Wrap panes in AppShell.tsx**

In `apps/web/src/shell/AppShell.tsx`, import `ErrorBoundary`:

```tsx
import { ErrorBoundary } from "./ErrorBoundary";
```

Then wrap each `<aside>` and `<section>` within the resizable panels:

```tsx
<ResizablePanel id="left" ...>
  <aside className="shell-panel">
    <ErrorBoundary label="Workspace">
      <WorkspacePane ... />
    </ErrorBoundary>
  </aside>
</ResizablePanel>

<ResizablePanel id="center" ...>
  <section className="shell-panel shell-panel--center">
    <ErrorBoundary label="Conversation">
      <ConversationPane ... />
    </ErrorBoundary>
  </section>
</ResizablePanel>

<ResizablePanel id="right" ...>
  <aside className="shell-panel">
    <ErrorBoundary label="Editor">
      <EditorPane ... />
    </ErrorBoundary>
  </aside>
</ResizablePanel>
```

- [ ] **Step 6: Run full web test suite**

```bash
npx vitest run
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/shell/ErrorBoundary.tsx apps/web/src/shell/__tests__/ErrorBoundary.test.tsx apps/web/src/shell/AppShell.tsx
git commit -m "Add ErrorBoundary to each shell pane (M3)"
```

---

## Task 3: Replace DiffViewer with react-diff-viewer-continued (I6)

**Files:**
- Modify: `apps/web/src/shell/editor/DiffViewer.tsx`

The current diff viewer uses two `<pre>` blocks with no line numbers, no character-level highlighting, and no synchronized scrolling. `react-diff-viewer-continued` is a drop-in replacement with all of these features.

- [ ] **Step 1: Install the package**

```bash
cd apps/web && npm install react-diff-viewer-continued
```

Verify it's in `package.json` dependencies.

- [ ] **Step 2: Write a render test for the new DiffViewer**

Create `apps/web/src/shell/editor/__tests__/DiffViewer.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DiffViewer } from "../DiffViewer";

describe("DiffViewer", () => {
  it("renders left and right titles", () => {
    render(
      <DiffViewer
        left="hello world"
        leftTitle="v1"
        right="hello there"
        rightTitle="v2"
      />
    );

    expect(screen.getByText("v1")).toBeTruthy();
    expect(screen.getByText("v2")).toBeTruthy();
  });

  it("renders diff content", () => {
    render(
      <DiffViewer
        left="line one\nline two\n"
        leftTitle="old"
        right="line one\nline three\n"
        rightTitle="new"
      />
    );

    // The library renders a table with the diff — both sides should be present
    expect(screen.getByText(/line one/)).toBeTruthy();
  });
});
```

Run: `npx vitest run src/shell/editor/__tests__/DiffViewer.test.tsx`

Expected: FAIL if the library isn't rendering yet (wrong import) or PASS if the old implementation passes the test. The test confirms the refactored component still renders correctly.

- [ ] **Step 3: Rewrite DiffViewer.tsx**

Replace the entire content of `apps/web/src/shell/editor/DiffViewer.tsx`:

```tsx
import ReactDiffViewer, { DiffMethod } from "react-diff-viewer-continued";

interface DiffViewerProps {
  left: string;
  leftTitle: string;
  right: string;
  rightTitle: string;
}

export function DiffViewer({ left, leftTitle, right, rightTitle }: DiffViewerProps) {
  return (
    <div className="diff-viewer">
      <ReactDiffViewer
        oldValue={left}
        newValue={right}
        leftTitle={leftTitle}
        rightTitle={rightTitle}
        splitView={true}
        compareMethod={DiffMethod.WORDS}
        useDarkTheme={false}
        styles={{
          variables: {
            light: {
              diffViewerBackground: "var(--color-surface)",
              diffViewerColor: "var(--color-ink)",
              addedBackground: "#e6ffec",
              addedColor: "#1a472a",
              removedBackground: "#ffebe9",
              removedColor: "#67060c",
              wordAddedBackground: "#acf2bd",
              wordRemovedBackground: "#fdb8c0",
            },
          },
        }}
      />
    </div>
  );
}
```

- [ ] **Step 4: Run DiffViewer tests**

```bash
npx vitest run src/shell/editor/__tests__/DiffViewer.test.tsx
```

Expected: both tests pass.

- [ ] **Step 5: Check that the web app builds**

```bash
npm run build
```

Expected: build succeeds with no TypeScript errors.

- [ ] **Step 6: Run full web test suite**

```bash
npx vitest run
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/ apps/web/package.json apps/web/package-lock.json
git commit -m "Replace hand-rolled DiffViewer with react-diff-viewer-continued (I6)"
```

---

## Task 4: Add form validation to workspace creation (I7)

**Files:**
- Modify: `apps/web/src/shell/panes/WorkspacePane.tsx`

The workspace creation form uses native `<form>` + `useState` with no validation. Introduce `react-hook-form` and `zod` to add field-level validation, error messages, and type-safe schema enforcement.

- [ ] **Step 1: Install packages**

```bash
npm install react-hook-form zod @hookform/resolvers
```

Verify all three are in `package.json` dependencies.

- [ ] **Step 2: Write a form validation test**

Create `apps/web/src/shell/panes/__tests__/WorkspacePane.test.tsx`:

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorkspacePane } from "../WorkspacePane";

const docTypes = [{ id: "prd", title: "PRD", has_skill: true, resource_groups: {} }];

describe("WorkspacePane workspace creation form", () => {
  it("shows validation error when description is empty and form is submitted", async () => {
    render(
      <WorkspacePane
        activeSession={null}
        activeTask={null}
        docTypes={docTypes}
        error={null}
        loading={false}
        nodes={[]}
        sessions={[]}
        onCreateSession={vi.fn()}
        onCreateWorkspace={vi.fn()}
        onOpenFile={vi.fn()}
        onSelectSession={vi.fn()}
        onSelectTask={vi.fn()}
      />
    );

    // Open the create form
    fireEvent.click(screen.getByLabelText("Create workspace"));

    // Clear the description field and submit
    const descriptionField = screen.getByLabelText("Description");
    fireEvent.change(descriptionField, { target: { value: "" } });
    fireEvent.submit(screen.getByRole("form", { name: /create workspace/i }));

    await waitFor(() => {
      expect(screen.getByText(/description is required/i)).toBeTruthy();
    });
  });

  it("calls onCreateWorkspace with form values when form is valid", async () => {
    const onCreateWorkspace = vi.fn().mockResolvedValue(undefined);
    render(
      <WorkspacePane
        activeSession={null}
        activeTask={null}
        docTypes={docTypes}
        error={null}
        loading={false}
        nodes={[]}
        sessions={[]}
        onCreateSession={vi.fn()}
        onCreateWorkspace={onCreateWorkspace}
        onOpenFile={vi.fn()}
        onSelectSession={vi.fn()}
        onSelectTask={vi.fn()}
      />
    );

    fireEvent.click(screen.getByLabelText("Create workspace"));

    const titleField = screen.getByLabelText("Title");
    fireEvent.change(titleField, { target: { value: "My PRD" } });

    const descriptionField = screen.getByLabelText("Description");
    fireEvent.change(descriptionField, { target: { value: "Build a search feature" } });

    fireEvent.submit(screen.getByRole("form", { name: /create workspace/i }));

    await waitFor(() => {
      expect(onCreateWorkspace).toHaveBeenCalledWith("prd", {
        title: "My PRD",
        description: "Build a search feature",
      });
    });
  });
});
```

- [ ] **Step 3: Run to confirm tests fail**

```bash
npx vitest run src/shell/panes/__tests__/WorkspacePane.test.tsx
```

Expected: FAIL — no aria-label on form, no validation errors yet.

- [ ] **Step 4: Rewrite the creation form in WorkspacePane.tsx**

At the top of `WorkspacePane.tsx`, add imports:

```tsx
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
```

Define the schema (add this near the top of the file, outside the component):

```tsx
const createWorkspaceSchema = z.object({
  docTypeId: z.string().min(1, "Document type is required"),
  title: z.string().min(1, "Title is required").max(80, "Title must be 80 characters or fewer"),
  description: z.string().min(1, "Description is required").max(2000, "Description must be 2000 characters or fewer"),
});

type CreateWorkspaceFormValues = z.infer<typeof createWorkspaceSchema>;
```

Replace the `creating` form state and `submitCreate` function in `WorkspacePane`:

```tsx
// Remove these lines:
// const [creating, setCreating] = useState(false);
// const [description, setDescription] = useState("...");
// const [title, setTitle] = useState("...");
// const [docTypeId, setDocTypeId] = useState(docTypes[0]?.id ?? "prd");

// Add:
const [creating, setCreating] = useState(false);
const {
  register,
  handleSubmit,
  reset,
  formState: { errors, isSubmitting },
} = useForm<CreateWorkspaceFormValues>({
  resolver: zodResolver(createWorkspaceSchema),
  defaultValues: {
    docTypeId: docTypes[0]?.id ?? "prd",
    title: "First usable imitation loop PRD",
    description: "Write a PRD for the first usable document imitation loop.",
  },
});

async function onSubmit(values: CreateWorkspaceFormValues) {
  await onCreateWorkspace(values.docTypeId, { title: values.title, description: values.description });
  setCreating(false);
  reset();
}
```

Replace the form JSX:

```tsx
{creating && (
  <form
    aria-label="Create workspace"
    className="workspace-create"
    onSubmit={handleSubmit(onSubmit)}
  >
    <Field>
      <FieldLabel htmlFor="workspace-doc-type">Document type</FieldLabel>
      <select id="workspace-doc-type" {...register("docTypeId")}>
        {docTypes.map((docType) => (
          <option key={docType.id} value={docType.id}>
            {docType.title}
          </option>
        ))}
      </select>
      {errors.docTypeId && (
        <p className="field-error body-sm">{errors.docTypeId.message}</p>
      )}
    </Field>
    <Field>
      <FieldLabel htmlFor="workspace-title">Title</FieldLabel>
      <Input
        aria-label="Title"
        id="workspace-title"
        {...register("title")}
      />
      <FieldDescription>Shown in the workspace list.</FieldDescription>
      {errors.title && (
        <p className="field-error body-sm">{errors.title.message}</p>
      )}
    </Field>
    <Field>
      <FieldLabel htmlFor="workspace-description">Description</FieldLabel>
      <Textarea
        aria-label="Description"
        id="workspace-description"
        {...register("description")}
      />
      <FieldDescription>Used as the agent brief inside the workspace.</FieldDescription>
      {errors.description && (
        <p className="field-error body-sm">{errors.description.message}</p>
      )}
    </Field>
    <Button type="submit" disabled={isSubmitting}>
      {isSubmitting ? "Creating…" : "Create workspace"}
    </Button>
  </form>
)}
```

Note: remove `onChange` handlers from Input and Textarea — `register` handles them.

- [ ] **Step 5: Add `.field-error` CSS class**

In `apps/web/src/shell/theme/shell.css`, add near the existing field styles:

```css
.field-error {
  color: var(--color-error, #b91c1c);
  margin-top: 2px;
}
```

- [ ] **Step 6: Run form validation tests**

```bash
npx vitest run src/shell/panes/__tests__/WorkspacePane.test.tsx
```

Expected: both tests pass.

- [ ] **Step 7: Run full web test suite and build**

```bash
npx vitest run && npm run build
```

Expected: all tests pass, build succeeds.

- [ ] **Step 8: Commit**

```bash
git add apps/web/src/ apps/web/package.json apps/web/package-lock.json
git commit -m "Add react-hook-form + zod validation to workspace creation form (I7)"
```

---

## Out of Scope (separate plans)

- **Assistant-UI integration** (Phase A–C from the review) — large effort, needs its own brainstorm + plan
- **M4** (SSE/WebSocket for timeline instead of 1.5s polling) — requires backend streaming endpoint
- **M5** (client-side routing / deep links) — requires React Router or similar; significant scope
- **I6 dark theme** — the `useDarkTheme={false}` prop in DiffViewer is hardcoded; tie to a theme toggle if/when one is added
