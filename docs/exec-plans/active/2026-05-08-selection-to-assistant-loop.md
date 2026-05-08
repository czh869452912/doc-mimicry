# Selection-To-Assistant Loop Plan

## Goal

Connect the right-side Markdown editor selection to the assistant-ui center thread so users can send selected text into the composer or ask the agent to revise the selection directly.

## Scope

- Restore the draft selection bar only when a real active session and real handlers exist.
- Add a "Send to chat" path that injects selected text into the assistant-ui composer for user editing before send.
- Add a "Revise" path that calls the existing `api.reviseSelection(sessionId, selectedText, instruction)` endpoint.
- Refresh timeline, workspace, and draft after revision actions.
- Add unit and E2E coverage for selection-to-chat and revise-selection flows.

## Non-goals

- Do not implement assistant-ui `SelectionToolbarPrimitive` floating selection UI in this pass.
- Do not add branch/candidate revision semantics.
- Do not add a full diff-review UI for revised selections.
- Do not change Markdown as the internal document format.

## Files and modules likely to change

- Modify `apps/web/src/shell/AppShell.tsx`
  - Pass real selection handlers into `EditorPane`.
  - Maintain a queued composer draft or direct queued command for selected text.
  - Call `api.reviseSelection` for direct revise.
- Modify `apps/web/src/shell/panes/ConversationPane.tsx`
  - Accept an optional queued composer draft and clear callback.
- Modify `apps/web/src/shell/assistant/DocAgentComposer.tsx`
  - Accept external draft text and set assistant-ui composer text through `useAui().composer().setText`.
- Modify `apps/web/src/shell/panes/EditorPane.tsx`
  - Pass handlers through as already supported.
- Modify `apps/web/src/shell/editor/tabs/DraftTab.tsx`
  - Adjust selection bar text if needed.
- Modify tests:
  - `apps/web/src/shell/__tests__/AppShell.test.tsx`
  - `apps/web/src/shell/assistant/__tests__/DocAgentComposer.test.tsx`
  - `apps/web/src/shell/editor/tabs/__tests__/DraftTab.test.tsx`
  - `apps/web/tests/core-loop.spec.ts`
- Modify `docs/reviews/active/2026-05-07-project-review-assistant-ui-integration.md`
  - Record the selection-to-assistant loop status.

## Step-by-step implementation checklist

### 1. Composer external draft injection

- [x] Write a failing `DocAgentComposer` test that renders `draftText="selected text prompt"` and expects the composer textarea to contain that text.
- [x] Add `draftText?: string | null` and `onDraftTextApplied?: () => void` props to `DocAgentComposer`.
- [x] In `DocAgentComposer`, call `aui.composer().setText(draftText)` in an effect when `draftText` is non-empty, focus the input, update slash query, then call `onDraftTextApplied`.
- [x] Pass these props through `ConversationPane`.
- [x] Run:

```powershell
cd apps\web
npm run test:unit -- src/shell/assistant/__tests__/DocAgentComposer.test.tsx
```

Expected: composer external draft injection test passes.

### 2. AppShell send selection to composer

- [x] Write a failing `AppShell` test that mocks `LazyDraftEditor`, selects text, clicks "Send to chat", and expects the center composer to contain a prompt with the selected text.
- [x] Add `queuedComposerDraft` state in `AppShell`.
- [x] Pass `onSendSelectionToChat` to `EditorPane`.
- [x] Format the prompt as:

```text
Please review this selected passage and suggest improvements:

> selected text
```

- [x] Pass `queuedComposerDraft` and clear callback into `ConversationPane`.
- [x] Run:

```powershell
cd apps\web
npm run test:unit -- src/shell/__tests__/AppShell.test.tsx
```

Expected: selection-to-composer test passes.

### 3. AppShell revise selection action

- [x] Write a failing `AppShell` test that selects text, clicks "Revise", and expects `api.reviseSelection("session-1", "selected text", "Please revise the selected passage while preserving its meaning.")`.
- [x] Add `reviseSelection` handling in `AppShell`.
- [x] After the API call, refresh timeline, workspace, and draft via existing refresh mechanisms.
- [x] Ensure no handler is passed when there is no active session.
- [x] Run:

```powershell
cd apps\web
npm run test:unit -- src/shell/__tests__/AppShell.test.tsx
```

Expected: revise selection test passes.

### 4. Selection bar copy and accessibility polish

- [x] Update `DraftTab` selection bar button labels if needed:
  - `Send to chat`
  - `Revise selection`
- [x] Ensure buttons remain hidden when handlers are absent.
- [x] Ensure selected text is cleared only by editor selection changes, not after button click.
- [x] Run:

```powershell
cd apps\web
npm run test:unit -- src/shell/editor/tabs/__tests__/DraftTab.test.tsx
```

Expected: DraftTab selection bar tests pass.

### 5. E2E coverage and docs

- [x] Add or extend Playwright coverage:
  - Reach draft-ready state.
  - Switch draft tab to Source.
  - Select or trigger a selection in the source editor.
  - Click `Send to chat` and verify composer contains selected text prompt, or use a deterministic test helper if CodeMirror selection is brittle.
  - Click `Revise selection` and verify a revise timeline event appears.
- [x] Update review doc to note the selection-to-assistant loop.
- [x] Run:

```powershell
cd apps\web
npm run test:unit
npm run build
npm run test:e2e
cd ..\..
.local\dev\.venv\Scripts\python.exe -m pytest -q
```

Expected: all verification passes.

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

- If CodeMirror selection is brittle in E2E, keep unit coverage for selection extraction and use E2E for the visible handler path that can be exercised deterministically.
- If revise endpoint behavior is too slow for E2E, assert the semantic timeline event via existing polling timeout rather than fixed sleeps.
- Do not reintroduce no-op selection handlers.

## Open questions

- Should the "Send to chat" prompt be Chinese or English? Initial implementation uses concise English to match existing UI copy.
- Should direct revise ask for a custom instruction? Not in this pass; use a default instruction and leave custom revision prompts for a later design.
