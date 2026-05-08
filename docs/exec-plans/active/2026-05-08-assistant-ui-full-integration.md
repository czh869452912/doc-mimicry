# Assistant-UI Full Integration Plan

## Goal

Make `@assistant-ui/react` the official center timeline and chat component for the authoring workbench. Replace the hand-written chat timeline and composer path in `ConversationPane`; do not maintain a parallel legacy renderer or compatibility DOM.

## Scope

- Replace the hand-written conversation stream with assistant-ui runtime and primitives.
- Keep DocAgent-specific semantics: slash commands, outline approval, checklist, artifact cards, approval cards, and semantic event pills.
- Treat timeline events as the backend source of truth, mapped into assistant-ui messages and custom data parts.
- Use assistant-ui's composer primitives for user input.
- Use assistant-ui thread/message/action primitives for message layout, auto-scroll, and message-level actions.
- Keep the existing three-pane authoring shell, workspace tree, editor, Markdown preview, diff viewer, and route state.

## Non-goals

- Do not preserve the current `StreamItem` render path as a runtime fallback.
- Do not keep hand-written `<textarea>` composer behavior after migration.
- Do not implement fake message branching before backend/session data can represent branches.
- Do not change backend timeline contracts unless a frontend blocker proves it is required.
- Do not implement DOCX/PDF export or PRD seed examples as part of this plan.

## Architecture

The center pane will become an assistant-ui thread hosted by a DocAgent runtime adapter.

```text
useTimeline(sessionId)
  -> TimelineEvent[]
  -> mapTimelineEventsToAssistantMessages()
  -> useExternalStoreRuntime()
  -> AssistantRuntimeProvider
  -> ThreadPrimitive / MessagePrimitive / MessagePartPrimitive / ComposerPrimitive
```

DocAgent keeps responsibility for domain-specific interpretation:

- `user_message` and `agent_message` become normal assistant-ui text messages.
- `propose_outline`, `run_checklist`, export events, and approval events become assistant-ui data parts rendered by DocAgent card components.
- Other semantic timeline events become compact assistant-ui data parts rendered as event rows.
- Slash commands run before model submission; unhandled input is sent through `api.sendMessage`.

## Files and modules likely to change

- Modify `apps/web/src/shell/panes/ConversationPane.tsx`
  - Replace legacy stream and composer with assistant-ui provider/primitives.
  - Keep only pane orchestration, slash help state, and handler wiring.
- Create `apps/web/src/shell/assistant/docAgentAssistantMessages.ts`
  - Own timeline-event to assistant-ui message/data-part mapping.
- Create `apps/web/src/shell/assistant/useDocAgentAssistantRuntime.ts`
  - Own `useExternalStoreRuntime` integration and submit handling.
- Create `apps/web/src/shell/assistant/DocAgentThread.tsx`
  - Own assistant-ui thread layout and message renderer composition.
- Create `apps/web/src/shell/assistant/DocAgentComposer.tsx`
  - Own assistant-ui composer controls and disabled states.
- Create `apps/web/src/shell/assistant/DocAgentMessageParts.tsx`
  - Own data-part renderers for event pills and existing cards.
- Modify `apps/web/src/shell/conversation/timelinePresentation.ts`
  - Either delete it or reduce it to pure event classification reused by assistant mapping.
- Modify `apps/web/src/shell/conversation/docagentRuntime.ts`
  - Keep merge/dedup helpers if still useful; move them only if the new assistant module becomes the clearer owner.
- Modify `apps/web/src/shell/theme/assistant-ui.css`
  - Expand from token bridge into complete assistant-ui thread/composer/card styling.
- Modify `apps/web/src/shell/theme/shell.css`
  - Remove stale `.conversation-stream`, `.message`, `.composer`, and legacy timeline styles once unused.
- Modify or create unit tests under `apps/web/src/shell/**/__tests__/`
  - Cover mapping, runtime submit behavior, composer behavior, and card rendering.
- Modify `apps/web/tests/workbench-shell.spec.ts`
  - Cover the assistant-ui center pane in the real workbench.
- Modify `docs/reviews/active/2026-05-07-project-review-assistant-ui-integration.md`
  - Update follow-up status after integration is complete.

## Step-by-step implementation checklist

### 1. Add test coverage for the required current behaviors

- [x] Add a focused `ConversationPane` or assistant-thread test that renders representative `Presentation`/timeline inputs:
  - user message
  - agent message
  - semantic event pill
  - outline card
  - checklist card
  - artifact card
  - approval card
- [x] Add a submit test that verifies plain text calls `api.sendMessage(session.id, input)`.
- [x] Add a slash-command test that verifies handled slash commands do not call `api.sendMessage`.
- [x] Add a disabled composer test for no active task.
- [x] Run:

```powershell
cd apps\web
npm run test:unit -- src/shell
```

Expected result: new tests pass against the current implementation before replacement starts, or fail only where the test intentionally describes the new assistant-ui DOM. If a test targets new DOM, keep it skipped only until the corresponding implementation task and remove the skip in that task.

### 2. Create the assistant message mapping layer

- [x] Create `apps/web/src/shell/assistant/docAgentAssistantMessages.ts`.
- [x] Define a discriminated data payload for DocAgent custom parts:

```ts
export type DocAgentAssistantData =
  | { kind: "event-pill"; category: PillCategory; summary: string; meta?: string; event: TimelineEvent }
  | { kind: "outline-card"; event: TimelineEvent }
  | { kind: "checklist-card"; event: TimelineEvent }
  | { kind: "artifact-card"; event: TimelineEvent }
  | { kind: "approval-card"; event: TimelineEvent };
```

- [x] Implement `mapTimelineEventsToAssistantMessages(events: TimelineEvent[]): ThreadMessage[]`.
- [x] Preserve stable IDs by using timeline event IDs for message IDs, not generated client IDs.
- [x] Use deterministic `new Date(0)` because the current `TimelineEvent` contract has no timestamp field.
- [x] Add tests for all known timeline event classes.
- [x] Run:

```powershell
cd apps\web
npm run test:unit -- src/shell/assistant
```

Expected result: mapping tests pass.

### 3. Build the DocAgent assistant runtime hook

- [x] Create `apps/web/src/shell/assistant/useDocAgentAssistantRuntime.ts`.
- [x] Use `useExternalStoreRuntime` from `@assistant-ui/react` with mapped messages from `useTimeline`.
- [x] Accept these inputs:

```ts
interface UseDocAgentAssistantRuntimeOptions {
  activeSession: SessionRecord | null;
  activeTask: TaskRecord | null;
  ensureSession: () => Promise<SessionRecord | null>;
  presentationsOrEvents: TimelineEvent[];
  onSubmitInput: (input: string) => Promise<void>;
}
```

- [x] Prefer passing raw `TimelineEvent[]` instead of `Presentation[]`; if the current call site only has presentations, update the call site to pass `events` from `useTimeline`.
- [x] Ensure submitted user text goes through the existing command path first:

```text
Composer submit -> submitInput(raw)
  -> executeSlashCommand(raw)
  -> if unhandled ensureSession()
  -> api.sendMessage(session.id, raw)
  -> refreshTimeline()
  -> refreshWorkspace() when send completes synchronously
```

- [x] Expose a status string or status model that `ConversationPane` can render outside the thread if needed.
- [x] Add tests with mocked `api.sendMessage`, `ensureSession`, `refreshTimeline`, and slash command handling.
- [x] Run:

```powershell
cd apps\web
npm run test:unit -- src/shell/assistant
```

Expected result: runtime hook tests pass.

### 4. Replace the thread renderer with assistant-ui primitives

- [x] Create `apps/web/src/shell/assistant/DocAgentThread.tsx`.
- [x] Use:
  - `AssistantRuntimeProvider`
  - `ThreadPrimitive.Root`
  - `ThreadPrimitive.Viewport`
  - `ThreadPrimitive.Messages`
  - `MessagePrimitive.Root`
  - `MessagePrimitive.Content`
  - `MessagePartPrimitive` renderers where needed
  - `ActionBarPrimitive` for copy/retry affordances where supported by the runtime
- [x] Keep the existing empty states, but render them as assistant-ui thread empty content rather than legacy stream elements.
- [x] Add assistant-ui auto-scroll by relying on thread viewport behavior and, where needed, `useThreadViewportAutoScroll`.
- [x] Remove the primary `presentations.map((presentation) => <StreamItem ... />)` path from `ConversationPane`.
- [x] Keep card components mounted only through assistant-ui custom part renderers.
- [x] Run:

```powershell
cd apps\web
npm run test:unit -- src/shell
npm run build
```

Expected result: tests and typecheck/build pass with assistant-ui primitives in the runtime bundle.

### 5. Replace the composer with assistant-ui primitives

- [x] Create `apps/web/src/shell/assistant/DocAgentComposer.tsx`.
- [x] Use:
  - `ComposerPrimitive.Root`
  - `ComposerPrimitive.Input`
  - `ComposerPrimitive.Send`
- [x] Preserve the current UX:
  - Enter submits.
  - Shift+Enter creates a newline.
  - send is disabled when no active task exists.
  - placeholder remains `Message the agent, or type / for commands`.
  - queued commands submit through the same path.
- [x] Remove `const [composer, setComposer] = useState("")` from `ConversationPane`.
- [x] Remove the hand-written `<textarea>` and `.send-button` form.
- [x] Add unit tests for submit and disabled behavior on the new composer.
- [x] Run:

```powershell
cd apps\web
npm run test:unit -- src/shell
npm run build
```

Expected result: tests and build pass.

### 6. Move DocAgent cards and event rows into assistant-ui custom part renderers

- [x] Create `apps/web/src/shell/assistant/DocAgentMessageParts.tsx`.
- [x] Render `DocAgentAssistantData` payloads with:
  - `OutlineCard`
  - `ChecklistCard`
  - `ArtifactCard`
  - `ApprovalCard`
  - event pill row
- [x] Keep handler props explicit:

```ts
interface DocAgentMessagePartRenderersProps {
  activeSessionId: string | null;
  taskId: string | null;
  onApproved: () => Promise<void>;
  onOpenPath: (path: string) => Promise<void>;
}
```

- [x] Ensure custom data parts do not render as opaque JSON or plain text fallback in normal cases.
- [x] Add tests that render each custom part and assert the user-visible label/action exists.
- [x] Run:

```powershell
cd apps\web
npm run test:unit -- src/shell/assistant
```

Expected result: custom part tests pass.

### 7. Delete the legacy chat/timeline path

- [x] Delete `StreamItem` from `ConversationPane.tsx`.
- [x] Delete or reduce `timelinePresentation.ts` so it no longer describes UI-level presentation objects. If kept, it should only export pure classification helpers like `categoryForKind`.
- [x] Remove the `ExternalThreadMessage` type-only bridge from `ConversationPane.tsx`; assistant-ui usage should be runtime imports and rendered primitives.
- [x] Remove stale CSS selectors:
  - `.conversation-stream` when no longer used
  - `.message`
  - `.message--user`
  - `.message--agent`
  - `.composer`
  - `.send-button`
  - any legacy event-row styles replaced by assistant-ui part styles
- [x] Confirm with search that `StreamItem` and legacy composer classes are gone.
- [x] Run:

```powershell
cd apps\web
npm run test:unit
npm run build
```

Expected result: full frontend unit suite and build pass.

### 8. Theme assistant-ui as the official center pane

- [x] Expand `apps/web/src/shell/theme/assistant-ui.css` to style:
  - thread root and viewport
  - empty state
  - user and assistant message surfaces
  - message content typography
  - event rows
  - custom cards within messages
  - composer root/input/send button
  - action bar
- [x] Keep the existing design principles from `docs/product/ui-surfaces.md`:
  - dense operational authoring surface
  - visible semantic timeline
  - no wizard-like flow
  - no decorative marketing layout
- [x] Avoid nested decorative cards; custom cards remain functional timeline items.
- [x] Run:

```powershell
cd apps\web
npm run build
```

Expected result: build passes.

### 9. Update E2E coverage

- [x] Modify `apps/web/tests/workbench-shell.spec.ts` to assert the new assistant-ui center pane:
  - renders the composer
  - sends a message
  - shows timeline updates
  - preserves deep-linked task/session state
  - renders at least one custom timeline card in the assistant-ui thread
- [x] Run:

```powershell
cd apps\web
npm run test:e2e
```

Expected result: all Playwright specs pass.

### 10. Update documentation and review status

- [x] Update `docs/reviews/active/2026-05-07-project-review-assistant-ui-integration.md`.
- [x] Replace the current "type/model preparation only" status with the actual assistant-ui runtime/primitive integration status.
- [x] Keep remaining non-goals explicit:
  - DOCX/PDF export still separate.
  - PRD examples/specs still separate.
  - durable external queue still separate.
  - BranchPicker remains pending unless backend branch semantics are implemented.
- [x] Add final verification commands to the review doc:

```powershell
cd apps\web
npm run test:unit
npm run build
npm run test:e2e
.local\dev\.venv\Scripts\python.exe -m pytest -q
```

Expected result: documentation matches implemented behavior without overclaiming unsupported assistant-ui features.

## Verification commands

Run after implementation:

```powershell
cd apps\web
npm run test:unit
npm run build
npm run test:e2e
cd ..\..
.local\dev\.venv\Scripts\python.exe -m pytest -q
```

Also run this repository structure check if any documentation-only follow-up is made:

```powershell
Get-ChildItem -Recurse -File | Select-Object FullName
```

## Rollback or recovery notes

- The rollback point is the commit before this plan is implemented.
- Because this plan intentionally removes the legacy renderer, rollback should use git revert of the assistant-ui integration commits rather than keeping a hidden runtime flag.
- If assistant-ui runtime API usage blocks progress, stop after the mapping layer and thread renderer tests, document the exact API mismatch, and either pin a compatible assistant-ui version or adjust to the exported v0.12.28 APIs.
- Do not restore the hand-written composer as a long-term fallback; a temporary local revert is acceptable only for diagnosis.

## Remaining Advanced Capability Backlog

The base assistant-ui migration is complete: the center pane now uses assistant-ui runtime, thread, message, composer, custom data parts, action bar, reload affordance, text attachments, and DocAgent-specific cards. The following high-order assistant-ui capabilities remain outside the completed migration.

### 1. Dictation

**Current state:** Not mounted. `useExternalStoreRuntime` does not yet receive a dictation adapter, and `DocAgentComposer` does not render `ComposerPrimitive.Dictate`, `ComposerPrimitive.StopDictation`, or `ComposerPrimitive.DictationTranscript`.

**Why it is still a gap:** assistant-ui can provide dictation through `WebSpeechDictationAdapter`, but Web Speech support is browser-dependent. The workbench must not show a dead microphone control in unsupported browsers or non-browser test environments.

**Implementation direction:**

- Configure `adapters.dictation` with `new WebSpeechDictationAdapter({ language: "zh-CN", interimResults: true })` only when `WebSpeechDictationAdapter.isSupported()` is true.
- Render dictate and stop controls only when dictation is available.
- Render interim transcript in the composer with `ComposerPrimitive.DictationTranscript`.
- Add unit coverage for both supported and unsupported capability states.

### 2. SelectionToolbar

**Current state:** Selection behavior is functionally wired through the CodeMirror-side selection bar. Users can send selected draft text to the assistant composer or trigger `reviseSelection`.

**Why it is still a gap:** The selection UI is not assistant-ui's `SelectionToolbarPrimitive`, so selection/quote behavior is not unified with the assistant-ui composer and message model.

**Implementation direction:**

- Keep CodeMirror as the source of selected text.
- Replace or wrap the existing editor selection bar with assistant-ui `SelectionToolbarPrimitive`.
- Preserve the two DocAgent commands: send selected text to composer and revise selection through the backend endpoint.
- Add E2E coverage for both actions after the primitive replacement.

### 3. Binary Attachments

**Current state:** Text-like attachments are complete. The composer accepts text/Markdown/CSV/JSON/XML/CSS/HTML, imports them through `api.importTextInput`, renders attachment chips, and includes imported Markdown paths in submitted messages.

**Why it is still a gap:** DOCX, PDF, images, and other binary inputs require a conversion pipeline, asset extraction policy, conversion reports, and error states. This overlaps with the Phase 0 import/export boundary work and should not be hidden behind a UI-only attachment affordance.

**Implementation direction:**

- Implement or reuse a backend binary import pipeline first.
- Extend the attachment adapter with file-type routing instead of broadening the current text adapter.
- Render conversion status and failures in assistant-ui attachment chips.
- Add E2E coverage for at least one binary import path once the backend conversion contract exists.

### 4. BranchPicker

**Current state:** Not mounted. The timeline is a single linear sequence. Reload resends the nearest previous user message as a new continuation.

**Why it is still a gap:** assistant-ui `BranchPickerPrimitive` needs real branch semantics: sibling responses, active branch selection, and stable parent/branch relationships. The current backend has sessions, timeline events, and draft versions, but no branch identifiers or branch-aware draft ownership.

**Implementation direction:**

- Design backend contracts for `parent_message_id`, `branch_id`, active branch selection, and branch-specific draft/checkpoint lineage.
- Expose branch metadata through the frontend assistant message mapping.
- Add assistant-ui BranchPicker only after the message repository can represent alternatives honestly.

### 5. Native Reload Semantics

**Current state:** Runtime `onReload` exists, and assistant messages expose a reload control inside `ActionBarPrimitive.Root`. This gives practical retry behavior by appending a new run from the previous user input.

**Why it is still a gap:** Full assistant-ui reload commonly implies replaying or replacing a branch from a parent message. DocAgent currently appends to the timeline, which is correct for the existing backend but not equivalent to branch-truncating retry.

**Implementation direction:**

- Keep current append-based reload until branch semantics exist.
- Once BranchPicker is implemented, decide whether reload should append, branch, or truncate a branch.
- Revisit `ActionBarPrimitive.Reload` after the message repository has enough semantic data to support native assistant-ui behavior.

### Recommended Order

1. Dictation.
2. SelectionToolbar.
3. Binary attachments.
4. BranchPicker.
5. Native reload semantics.
