# Assistant-UI Attachments Implementation Plan

> **Archive note (2026-05-17):** This completed plan preserves its original
> execution checklist for historical traceability. Any unchecked boxes below are
> not active work; use active plan/review directories for current tasks.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire assistant-ui composer attachment primitives to real DocAgent workspace input imports.

**Architecture:** Add a DocAgent text attachment adapter and pass it to `useExternalStoreRuntime` through `adapters.attachments`. The adapter reads text-like files, imports them through the existing `/tasks/{task_id}/inputs/text` API on send, and converts the completed attachment into text content that references the imported Markdown path.

**Tech Stack:** React 19, TypeScript, `@assistant-ui/react`, Vitest, Playwright, existing DocAgent text input import API.

---

## Scope

- Accept text-like files from the assistant-ui composer.
- Render attachment chips through `ComposerPrimitive.Attachments`.
- Support removing pending attachments through assistant-ui attachment state.
- Import attachments into `inputs/markdown/` before sending the composer message.
- Include imported attachment references in the submitted message text.
- Refresh workspace and timeline through the existing send path.

## Non-Goals

- Do not implement binary DOCX/PDF/image import in this pass.
- Do not add backend endpoints.
- Do not store attachments only in frontend state without importing them to the workspace.
- Do not implement branch-aware attachment history.

## Tasks

### Task 1: Attachment Adapter

- [ ] Create `apps/web/src/shell/assistant/docAgentAttachmentAdapter.ts`.
- [ ] Implement a text attachment adapter with `accept` for text-like extensions and MIME types.
- [ ] Read files during `add()` for validation and display.
- [ ] Import files during `send()` using `api.importTextInput(taskId, attachment.name, text)`.
- [ ] Return a complete attachment whose content is a text part referencing `result.markdown_path`.
- [ ] Add unit tests for add/send/no-task behavior.

### Task 2: Runtime Wiring

- [ ] Add `activeTaskId` to `useDocAgentAssistantRuntime` options.
- [ ] Memoize and pass the DocAgent adapter via `adapters.attachments`.
- [ ] Ensure attachments are included in `AppendMessage.content` and converted by `textFromAppendMessage`.
- [ ] Add unit/integration coverage for sending a message with an attachment.

### Task 3: Composer UI

- [ ] Add `ComposerPrimitive.AttachmentDropzone`.
- [ ] Add `ComposerPrimitive.AddAttachment` button.
- [ ] Add `ComposerPrimitive.Attachments` chips with attachment name/status and remove control.
- [ ] Style attachment controls in `assistant-ui.css`.
- [ ] Add composer unit tests for the attach affordance and rendered pending file.

### Task 4: E2E And Docs

- [ ] Add Playwright coverage that uploads a text file, sends it, sees the imported reference in the thread, and sees the imported workspace input path.
- [ ] Update `docs/reviews/completed/2026-05-07-project-review-assistant-ui-integration.md`.
- [ ] Run full verification.

## Verification

```powershell
cd apps\web
npm run test:unit
npm run build
npm run test:e2e
cd ..\..
.local\dev\.venv\Scripts\python.exe -m pytest -q
```
