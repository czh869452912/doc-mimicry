# Assistant-UI Reload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire assistant-ui reload actions to a real DocAgent behavior by resending the nearest prior user message and refreshing the thread.

**Architecture:** Use the assistant-ui ActionBar surface inside assistant messages and `useExternalStoreRuntime`'s `onReload(parentId)` callback. The frontend derives retry input from existing `TimelineEvent[]`; no backend retry API is added in this pass.

**Tech Stack:** React 19, TypeScript, `@assistant-ui/react`, Vitest, Playwright.

---

## Scope

- Add reload action to assistant messages.
- Keep copy action on user and assistant messages.
- Add an `onReloadInput(parentMessageId)` path through `useDocAgentAssistantRuntime` and `ConversationPane`.
- Find the nearest previous `user_message` event before the target assistant message and send it through the existing `/messages?background=true` path.
- Refresh timeline after reload.
- Show a clear status if there is no user message to retry.

## Non-Goals

- Do not add backend retry endpoints.
- Do not truncate or branch timeline.
- Do not implement BranchPicker in this pass.
- Do not implement edit-and-resubmit.

## Tasks

### Task 1: Runtime Reload Mapping

- [x] Add `onReloadInput?: (parentMessageId: string | null) => Promise<void>` to `useDocAgentAssistantRuntime`.
- [x] Pass it to `useExternalStoreRuntime` as `onReload`.
- [x] Add unit/integration coverage in `AppShell.test.tsx` that clicking reload resends the previous user message.

### Task 2: Assistant Message Reload Button

- [x] Add a reload control to assistant message actions inside `ActionBarPrimitive.Root`.
- [x] Keep reload off user messages.
- [x] Reuse message-action styles and add an accessible label.

### Task 3: E2E And Docs

- [x] Extend E2E to verify reload is visible and resends a message.
- [x] Update review doc to remove retry/reload from open assistant-ui gaps at current semantics.
- [x] Run full verification.

## Verification

```powershell
cd apps\web
npm run test:unit
npm run build
npm run test:e2e
cd ..\..
.local\dev\.venv\Scripts\python.exe -m pytest -q
```
