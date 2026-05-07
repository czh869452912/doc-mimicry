# Workbench Left Rail And shadcn Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix workspace creation and session navigation semantics, then migrate the shell toward a high-quality shadcn/ui component layer without disrupting the document-agent workbench model.

**Architecture:** Keep the authoring shell as a thin React composition over the existing FastAPI REST API and workspace contract. Split the left rail into separate workspaces, sessions, and workspace files surfaces instead of mixing sessions into the file tree. Introduce shadcn/ui incrementally as the reusable UI component layer while keeping `react-arborist`, `react-resizable-panels`, CodeMirror, and assistant-ui for their specialized domains.

**Tech Stack:** FastAPI, Pydantic, React 19, Vite 7, TypeScript 5.8, Vitest, Testing Library, shadcn/ui, Radix primitives, cmdk, react-arborist, react-resizable-panels, CodeMirror.

---

## Goal

The finished work should let a user:

1. Create a workspace with a distinct title and description.
2. See workspace title in the left rail and top bar, while description remains the agent brief.
3. Create a new session under the currently selected workspace.
4. View and switch sessions in a dedicated Sessions section, separate from the workspace file tree.
5. Open workspace files from a file tree that only contains files and folders.
6. Avoid draft autosave writes caused only by backend draft hydration.
7. Use a growing shared UI component layer instead of hand-built buttons, fields, badges, empty states, sheets, command menus, and tabs.

## Scope

- Add `title` and `description` to task records while preserving `brief` as a compatibility alias for the agent workspace brief.
- Keep existing `POST /tasks` clients working with `{ doc_type_id, brief }`.
- Add frontend support for `{ title, description }` workspace creation.
- Add an explicit "New session" action for the active workspace using the existing `POST /tasks/{task_id}/sessions` endpoint.
- Move sessions out of `react-arborist` file tree data.
- Add focused regression tests for title/description, session creation, tree separation, doc type default selection, and autosave hydration.
- Initialize shadcn/ui in the Vite app and migrate selected shell primitives incrementally.

## Non-Goals

- No workflow engine, DAG builder, or document-type-specific fixed flow.
- No change to the workspace file contract.
- No database migration layer; Phase 1 state is still JSON file state under `.local/docagent`.
- No complete visual redesign of all panes in this pass.
- No replacement of `react-arborist`, `react-resizable-panels`, CodeMirror, or assistant-ui.
- No Tailwind-heavy app restyle before shadcn initialization is verified in this repo.

## Files And Modules Likely To Change

### Backend

- `services/api/docagent_api/app.py`
  - Accept `title` and `description` in `CreateTaskRequest`.
  - Preserve `brief` compatibility.
  - Normalize task responses.
- `services/api/docagent_api/state.py`
  - Normalize old task records returned from `list_tasks()` and `get_task()`.
- `services/api/tests/test_api.py`
  - Cover new task creation contract and legacy brief compatibility.

### Frontend API And Types

- `apps/web/src/api.ts`
  - Allow `api.createTask(docTypeId, { title, description })`.
  - Preserve `api.createTask(docTypeId, brief)` compatibility.
- `apps/web/src/types.ts`
  - Add optional `title` and `description` fields to `TaskRecord`.

### Shell State And Panes

- `apps/web/src/shell/state/useWorkspaces.ts`
  - Add `CreateWorkspaceInput`.
  - Add `createSessionForActiveTask()`.
  - Use `task.title ?? task.brief` for workspace labels.
  - Remove sessions from workspace tree node children.
- `apps/web/src/shell/panes/WorkspacePane.tsx`
  - Use separate Title and Description fields.
  - Sync default doc type after async doc type loading.
  - Add Sessions section and New session action.
  - Keep file tree scoped to files/folders.
- `apps/web/src/shell/AppShell.tsx`
  - Show workspace title in the top bar.
  - Wire `createSessionForActiveTask`.
- `apps/web/src/shell/editor/useAutoSave.ts`
  - Reset saved baseline when `taskId` changes and hydrated draft becomes active.

### UI Component Layer

- `apps/web/components.json`
  - shadcn/ui project config after initialization.
- `apps/web/src/components/ui/*`
  - shadcn/ui components added through CLI.
- `apps/web/src/lib/utils.ts`
  - `cn` helper if shadcn initialization creates it.
- `apps/web/src/shell/ui/*`
  - Temporary local shadcn-like wrappers, removed or replaced after official components are available.
- `apps/web/src/shell/theme/*.css`
  - Bridge existing design tokens to shadcn semantic tokens.

### Tests

- `apps/web/src/shell/__tests__/AppShell.test.tsx`
- `apps/web/src/shell/__tests__/useWorkspaces.test.tsx`
- `apps/web/src/shell/__tests__/WorkspacePane.test.tsx`
- `apps/web/tests/workbench-shell.spec.ts`

## Task 1: Patch Workspace And Session Semantics

**Files:**
- Modify: `services/api/docagent_api/app.py`
- Modify: `services/api/docagent_api/state.py`
- Modify: `services/api/tests/test_api.py`
- Modify: `apps/web/src/api.ts`
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/shell/state/useWorkspaces.ts`
- Modify: `apps/web/src/shell/panes/WorkspacePane.tsx`
- Modify: `apps/web/src/shell/AppShell.tsx`
- Modify: `apps/web/src/shell/editor/useAutoSave.ts`
- Modify: `apps/web/src/shell/__tests__/AppShell.test.tsx`
- Modify: `apps/web/src/shell/__tests__/useWorkspaces.test.tsx`
- Modify: `apps/web/src/shell/__tests__/WorkspacePane.test.tsx`

- [x] Step 1: Add failing frontend tests for distinct title/description creation, new session action, session/file-tree separation, and draft hydration not autosaving.

Run:

```powershell
cd apps/web
npm run test:unit -- src/shell/__tests__/AppShell.test.tsx src/shell/__tests__/useWorkspaces.test.tsx
```

Expected before implementation: FAIL because title is not used, sessions are in tree data, no New session button exists, and draft hydration triggers `api.updateDraft`.

- [x] Step 2: Add a backend regression test for `POST /tasks` with `title` and `description`.

Test behavior:

```python
response = client.post(
    "/tasks",
    json={
        "doc_type_id": "prd",
        "title": "Billing controls PRD",
        "description": "Write a PRD for enterprise billing controls.",
    },
)
assert response.status_code == 200
assert response.json()["title"] == "Billing controls PRD"
assert response.json()["description"] == "Write a PRD for enterprise billing controls."
assert response.json()["brief"] == "Write a PRD for enterprise billing controls."
```

- [x] Step 3: Implement backend compatibility.

Implementation requirements:

- `CreateTaskRequest` accepts `brief`, `title`, and `description`.
- `description = request.description or request.brief`.
- Empty description returns HTTP 422.
- `brief` is stored as the description for compatibility.
- `title` defaults to the first non-empty description line truncated to 80 characters.
- `DocAgentState.list_tasks()` and `get_task()` normalize old records with missing `title` or `description`.

- [x] Step 4: Implement frontend API and type changes.

Implementation requirements:

- `TaskRecord` has optional `title?: string` and `description?: string`.
- `api.createTask(docTypeId, input)` accepts either a legacy string brief or `{ title, description }`.

- [x] Step 5: Implement left rail behavior.

Implementation requirements:

- `WorkspacePane` create form has Document type, Title, and Description fields.
- Default document type syncs after async `docTypes` loading.
- `useWorkspaces.buildWorkspaceTreeData()` uses task title and no longer adds session nodes.
- `WorkspacePane` receives `sessions` separately and renders a Sessions section.
- `WorkspacePane` exposes a `New session` action.
- `useWorkspaces` exposes `createSessionForActiveTask()`.
- `AppShell` wires `createSessionForActiveTask()` and uses title in `TopBar`.

- [x] Step 6: Implement autosave baseline fix.

Implementation requirement:

- `useAutoSave` resets `lastSaved.current` and `saveState` when `taskId` changes and autosave becomes enabled, preventing hydrated drafts from being treated as user edits.

- [x] Step 7: Run focused frontend verification.

Run:

```powershell
cd apps/web
npm run test:unit -- src/shell/__tests__/AppShell.test.tsx src/shell/__tests__/useWorkspaces.test.tsx src/shell/__tests__/WorkspacePane.test.tsx
npm run build
```

Expected: unit tests pass and build exits 0. Existing third-party `"use client"` and chunk-size warnings are acceptable if unchanged.

- [x] Step 8: Run backend verification.

Run from repo root with the Python environment that has pytest installed:

```powershell
python -m pytest services/api/tests/test_api.py::test_task_creation_keeps_title_separate_from_description -q
```

Expected: PASS. If local Python lacks pytest, record the exact interpreter and error in implementation notes.

## Task 2: Formalize shadcn/ui In The Web App

**Files:**
- Create: `apps/web/components.json`
- Create or modify: `apps/web/src/lib/utils.ts`
- Modify: `apps/web/src/styles.css`
- Modify: `apps/web/src/shell/theme/tokens.css`
- Modify: `apps/web/package.json`
- Modify: `apps/web/package-lock.json`

- [x] Step 1: Inspect current shadcn context.

Run:

```powershell
cd apps/web
npx shadcn@latest info --json
```

Actual: the first `info --json` failed until `components.json` aliases were changed to `@/...`; after that, the CLI resolved the project.

- [x] Step 2: Initialize shadcn/ui for a Vite React app.

Run:

```powershell
cd apps/web
npx shadcn@latest init
```

Selection requirements:

- TypeScript: yes.
- Framework/template: Vite or manual Vite React if prompted.
- Base: Radix.
- Icon library: lucide.
- CSS file: `src/styles.css`.
- Components path: `src/components/ui`.
- Utilities path: `src/lib/utils.ts`.

Actual: the interactive Vite init did not detect this existing app, so initialization was completed manually with `components.json`, `src/lib/utils.ts`, TypeScript paths, and Vite alias config.

- [x] Step 3: If initialization requires Tailwind, choose the smallest compatible path.

Preferred path:

- Install only the Tailwind dependencies required by shadcn's Vite setup.
- Keep existing shell CSS imports working.
- Map existing design tokens into shadcn semantic variables rather than replacing the app theme wholesale.

Recovery path:

- If Tailwind initialization conflicts with Vite 7 or React 19, pause and record the error before changing production UI.

- [x] Step 4: Verify after initialization.

Run:

```powershell
cd apps/web
npm run build
npm run test:unit -- src/shell/__tests__/AppShell.test.tsx src/shell/__tests__/useWorkspaces.test.tsx src/shell/__tests__/WorkspacePane.test.tsx
```

Expected: build and focused tests pass.

## Task 3: Add And Use Core shadcn Components

**Files:**
- Create: `apps/web/src/components/ui/button.tsx`
- Create: `apps/web/src/components/ui/input.tsx`
- Create: `apps/web/src/components/ui/textarea.tsx`
- Create: `apps/web/src/components/ui/select.tsx`
- Create: `apps/web/src/components/ui/badge.tsx`
- Create: `apps/web/src/components/ui/empty.tsx`
- Create: `apps/web/src/components/ui/sheet.tsx`
- Create: `apps/web/src/components/ui/command.tsx`
- Create: `apps/web/src/components/ui/tabs.tsx`
- Create: `apps/web/src/components/ui/resizable.tsx`
- Modify: `apps/web/src/shell/panes/WorkspacePane.tsx`
- Modify: `apps/web/src/shell/CommandPalette.tsx`
- Modify: `apps/web/src/shell/SettingsDrawer.tsx`
- Modify: `apps/web/src/shell/panes/EditorPane.tsx`
- Modify: `apps/web/src/shell/AppShell.tsx`
- Delete later: `apps/web/src/shell/ui/Button.tsx`
- Delete later: `apps/web/src/shell/ui/Field.tsx`
- Delete later: `apps/web/src/shell/ui/Empty.tsx`
- Delete later: `apps/web/src/shell/ui/Badge.tsx`

- [x] Step 1: Add official components through the CLI.

Run:

```powershell
cd apps/web
npx shadcn@latest add button input textarea select badge empty sheet command tabs resizable
```

Expected: files are created under `src/components/ui`.

- [x] Step 2: Review generated component files.

Check:

- Imports use this project's configured alias or relative paths that compile.
- Components use `lucide-react` where icons are needed.
- No generated file assumes Next.js server components.
- `npm run build` compiles after generation.

- [x] Step 3: Replace temporary local wrappers in `WorkspacePane`.

Implementation requirements:

- Replace `../ui/Button` with `src/components/ui/button`.
- Replace local Field usage with shadcn-style field composition if `field` is available; otherwise use `Label` plus `Input`/`Textarea` from shadcn.
- Replace local `Empty` and `Badge` with official components.
- Remove `apps/web/src/shell/ui/*` only after no imports remain.

- [ ] Step 4: Replace overlay primitives where useful.

Deferred: official `sheet`, `command`, `tabs`, and `resizable` components were added and build-verified, but `SettingsDrawer`, `CommandPalette`, `EditorPane`, and `AppShell` were not migrated in this pass to keep behavior risk contained.

Implementation requirements:

- `CommandPalette` uses shadcn `Command` composed inside `Dialog` or existing overlay if preserving behavior is lower risk.
- `SettingsDrawer` uses shadcn `Sheet`.
- `EditorPane` uses shadcn `Tabs` only if the API matches current Radix behavior without regressions.
- `AppShell` may use shadcn `Resizable` wrappers around `react-resizable-panels` if it reduces custom styling.

- [x] Step 5: Run focused tests and build.

Run:

```powershell
cd apps/web
npm run test:unit -- src/shell/__tests__/AppShell.test.tsx src/shell/__tests__/useWorkspaces.test.tsx src/shell/__tests__/WorkspacePane.test.tsx
npm run build
```

Expected: tests and build pass.

## Task 4: Extend Smoke Coverage

**Files:**
- Modify: `apps/web/tests/workbench-shell.spec.ts`

- [x] Step 1: Update Playwright smoke selectors for title and description.

Smoke should cover:

```ts
await page.getByRole("button", { name: /create workspace/i }).click();
await page.getByLabel(/title/i).fill("First loop PRD");
await page.getByLabel(/description/i).fill("Write a PRD for the first usable document imitation loop.");
await page.getByRole("button", { name: /^create workspace$/i }).click();
await expect(page.getByText("First loop PRD")).toBeVisible();
```

- [x] Step 2: Add session creation smoke.

Smoke should cover:

```ts
await page.getByRole("button", { name: /new session/i }).click();
await expect(page.getByText(/session-/i)).toBeVisible();
await expect(page.getByText("Workspace files")).toBeVisible();
```

- [x] Step 3: Run e2e smoke if local dev server and browser binaries are available.

Run:

```powershell
cd apps/web
npm run test:e2e
```

Expected: smoke tests pass. If Playwright browser binaries are missing, install Chromium with `npx playwright install chromium` and rerun.

## Verification Commands

Frontend focused:

```powershell
cd apps/web
npm run test:unit -- src/shell/__tests__/AppShell.test.tsx src/shell/__tests__/useWorkspaces.test.tsx src/shell/__tests__/WorkspacePane.test.tsx
npm run build
```

Frontend full:

```powershell
cd apps/web
npm run test:unit
npm run test:e2e
```

Backend focused:

```powershell
python -m pytest services/api/tests/test_api.py::test_task_creation_keeps_title_separate_from_description -q
```

Backend regression:

```powershell
python -m pytest packages/contracts/tests packages/workspace/tests packages/timeline/tests tools/import/tests services/api/tests agent/runtime-adapters/mock/tests tests -q
```

Documentation structure check:

```powershell
Get-ChildItem -Recurse -File | Select-Object FullName
```

## Rollback Or Recovery Notes

- If `title`/`description` causes old task reads to fail, keep the backend response normalization and avoid rewriting stored JSON immediately.
- If a client still posts `{ brief }`, backend must continue accepting it.
- If shadcn initialization introduces a Tailwind setup that breaks existing CSS, revert only Task 2 and keep Task 1 behavior changes.
- If shadcn CLI fails because of npm cache extraction errors, clear the npx cache or install `shadcn` as a dev tool only after recording the exact error.
- If official shadcn components require broad Tailwind migration, keep the temporary local wrappers and schedule a separate style-system migration.

## Open Questions

- Should sessions eventually have user-facing titles, or is id/status enough for Phase 1?
- Should workspace `title` be editable after creation in this phase?
- Should `description` replace all user-facing uses of `brief`, or should `brief` remain visible in debug/runtime surfaces?
- Should shadcn be initialized with Tailwind v4 defaults, or should this repo pin a conservative Tailwind setup for Vite 7?

## Current Notes

- Task 1 frontend focused verification has already passed in this workspace:

```powershell
cd apps/web
npm run test:unit -- src/shell/__tests__/AppShell.test.tsx src/shell/__tests__/useWorkspaces.test.tsx src/shell/__tests__/WorkspacePane.test.tsx
npm run build
```

- The system Python interpreters did not have `pytest` installed:

```text
C:\msys64\ucrt64\bin\python.exe: No module named pytest
C:\Users\fai_l\AppData\Local\Programs\Python\Python38\python.exe: No module named pytest
```

- Backend verification passed with the repository dev venv:

```powershell
.\.local\dev\.venv\Scripts\python.exe -m pytest services/api/tests/test_api.py
```

Result: 4 passed.

- shadcn/ui formalization completed with Vite + Tailwind v4. `npx shadcn@latest info --json` reports these installed components:

```text
badge, button, command, dialog, empty, field, input, label, resizable, select, separator, sheet, tabs, textarea, tooltip
```

- The generated `resizable` component expected old `PanelGroup` / `PanelResizeHandle` export names. It was adapted to the installed `react-resizable-panels@4.11.0` exports: `Group`, `Panel`, and `Separator`.

- Current frontend verification after shadcn migration:

```powershell
cd apps/web
npm run test:unit -- src/shell/__tests__/AppShell.test.tsx src/shell/__tests__/useWorkspaces.test.tsx src/shell/__tests__/WorkspacePane.test.tsx
npm run build
```

Result: 3 test files / 10 tests passed; build exited 0 with the existing large chunk warning.

- Playwright smoke coverage was extended to create a workspace with a unique title and description, create a new session, and assert the dedicated Sessions and Workspace files surfaces. The e2e config now starts both FastAPI and Vite so smoke tests cover the real local REST contract.

```powershell
cd apps/web
npm run test:e2e
```

Result: 2 passed.
