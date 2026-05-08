# Assistant-UI Interaction Hardening Plan

## Goal

Polish the assistant-ui center pane after the runtime/primitive migration by improving slash command discovery, message actions, running/loading states, and semantic timeline card styling without adding backend-dependent features.

## Scope

- Add visible slash command suggestions to the assistant-ui composer for the existing `SLASH_COMMANDS`.
- Add assistant-ui message copy actions for text messages.
- Improve running/loading/empty states inside the assistant-ui thread and composer.
- Tighten styling for event pills and custom timeline cards rendered as assistant-ui data parts.
- Add unit and E2E coverage for the hardened interaction states.
- Update the review document with the new status.

## Non-goals

- Do not enable BranchPicker until backend/session branch semantics exist.
- Do not enable retry/reload until retry has a correct backend contract.
- Do not enable attachments or dictation in this pass.
- Do not reintroduce hand-written chat/timeline rendering.

## Files and modules likely to change

- Modify `apps/web/src/shell/assistant/DocAgentComposer.tsx`
  - Add slash command suggestions and selected command insertion.
- Create `apps/web/src/shell/assistant/DocAgentSlashCommands.tsx`
  - Own filtering and rendering of slash command suggestions.
- Modify `apps/web/src/shell/assistant/DocAgentThread.tsx`
  - Add message action bar with copy action.
  - Render running/loading state inside the thread.
- Modify `apps/web/src/shell/assistant/DocAgentMessageParts.tsx`
  - Add a stable wrapper class for semantic timeline cards and event rows.
- Modify `apps/web/src/shell/panes/ConversationPane.tsx`
  - Pass running/loading state into assistant-ui components.
  - Remove redundant external status text where assistant-ui state now covers it.
- Modify `apps/web/src/shell/theme/assistant-ui.css`
  - Style command suggestions, action bar, running state, and timeline parts.
- Modify tests under `apps/web/src/shell/assistant/__tests__/` and `apps/web/src/shell/panes/__tests__/`
  - Cover suggestions, copy action presence, running state, and semantic part wrappers.
- Modify `apps/web/tests/workbench-shell.spec.ts`
  - Cover slash suggestion visibility and center pane interaction.
- Modify `docs/reviews/active/2026-05-07-project-review-assistant-ui-integration.md`
  - Update assistant-ui advanced capability status.

## Step-by-step implementation checklist

### 1. Composer slash command suggestions

- [x] Write a failing test for `DocAgentComposer` that types `/` and expects `/start`, `/check`, `/export`, and `/help` suggestions.
- [x] Create `DocAgentSlashCommands.tsx` with a controlled input observer:
  - Read the active textarea value through composer input events.
  - Show suggestions only when the current value starts with `/`.
  - Filter by command prefix.
  - On click, replace composer input text with the command plus a trailing space and focus the textarea.
- [x] Wire `DocAgentSlashCommands` into `DocAgentComposer`.
- [x] Run:

```powershell
cd apps\web
npm run test:unit -- src/shell/assistant
```

Expected: assistant component tests pass.

### 2. Message copy action bar

- [x] Write a failing `DocAgentThread`/`ConversationPane` test that renders a text message and expects a copy button in the assistant-ui message action area.
- [x] Add `ActionBarPrimitive.Root` and `ActionBarPrimitive.Copy` to user and assistant text message renderers.
- [x] Hide retry/reload controls in this pass.
- [x] Style the action bar so it is compact and non-disruptive in the dense center pane.
- [x] Run:

```powershell
cd apps\web
npm run test:unit -- src/shell/assistant src/shell/panes/__tests__/ConversationPane.test.tsx
```

Expected: action bar tests pass.

### 3. Running and loading state hardening

- [x] Write a failing `ConversationPane` test for an active running session that expects an in-thread running indicator.
- [x] Pass `isRunning` and `loading` into `DocAgentThread`.
- [x] Render a compact in-thread status row when timeline is loading or session status starts with `running`.
- [x] Keep the status row semantic and concise; do not show duplicate `Working...` text outside the thread when the in-thread state is visible.
- [x] Run:

```powershell
cd apps\web
npm run test:unit -- src/shell/panes/__tests__/ConversationPane.test.tsx
```

Expected: running/loading state tests pass.

### 4. Semantic part styling

- [x] Write or update tests to assert event rows and cards have assistant-ui-specific wrapper classes.
- [x] Wrap custom data parts with `.aui-timeline-part`.
- [x] Use `.aui-timeline-part--event`, `.aui-timeline-part--card`, and existing `inline-card` internals.
- [x] Update `assistant-ui.css` so event rows and cards align with message spacing and do not appear as legacy stream remnants.
- [x] Run:

```powershell
cd apps\web
npm run test:unit -- src/shell/assistant
```

Expected: semantic part tests pass.

### 5. E2E and documentation

- [x] Extend `apps/web/tests/workbench-shell.spec.ts`:
  - Type `/` into composer and verify slash suggestions appear.
  - Verify an assistant-ui copy action is present after a message appears.
  - Verify no legacy `.conversation-stream` exists.
- [x] Update the review document to note:
  - Slash command discovery is integrated.
  - Copy action is enabled.
  - Retry, BranchPicker, attachments, dictation, and SelectionToolbar remain intentionally deferred.
- [x] Run:

```powershell
cd apps\web
npm run test:unit
npm run build
npm run test:e2e
cd ..\..
.local\dev\.venv\Scripts\python.exe -m pytest -q
```

Expected: all frontend and backend verification passes.

## Verification commands

```powershell
cd apps\web
npm run test:unit
npm run build
npm run test:e2e
cd ..\..
.local\dev\.venv\Scripts\python.exe -m pytest -q
```

## Rollback or recovery notes

- Revert this hardening commit if suggestions or action bars regress composer submission.
- Do not restore the legacy conversation stream.
- If assistant-ui copy primitive behaves inconsistently in jsdom, keep the production primitive and assert the accessible copy button exists rather than testing clipboard contents.

## Open questions

- Should slash suggestions eventually use assistant-ui's unstable trigger popover primitives? Yes, but only after this lightweight suggestion layer proves the command UX.
- Should retry be added after copy? Not in this round; it needs a backend retry contract.
