# External ACP UI Embed Plan

## Goal

Use an existing ACP client UI for the center agent interaction surface wherever possible, while keeping DocAgent's document workspace, Markdown preview/editor, and product-specific panels in the existing React workbench.

The low-cost path is to treat `acp-ui` or a similar ACP client as a separately maintained web app embedded by URL, not as code translated into DocAgent React components.

## Scope

- Add a configurable iframe bridge in `apps/web` for an external ACP UI URL.
- Keep the current local ACP surface as a fallback when no external URL is configured.
- Stop obvious OpenHands housekeeping events from becoming visible center-pane noise.
- Document the intended next step: a small ACP-over-WebSocket gateway that lets `acp-ui` talk to DocAgent sessions.

## Non-goals

- Do not rewrite DocAgent's full product shell around `acp-ui`.
- Do not port Vue `acp-ui` components into React.
- Do not build a custom polished agent timeline in this change.
- Do not expose OpenHands runtime internals directly to the browser as the durable product contract.

## Files and modules likely to change

- `apps/web/src/shell/acp/AcpUiEmbed.tsx`
- `apps/web/src/shell/acp/acpUiEmbed.ts`
- `apps/web/src/shell/panes/ConversationPane.tsx`
- `apps/web/src/shell/theme/acp.css`
- `apps/web/src/vite-env.d.ts`
- `agent/runtime-adapters/openhands/docagent_openhands_runtime/adapter.py`
- `agent/runtime-adapters/openhands/tests/test_openhands_adapter.py`
- `apps/web/src/shell/acp/__tests__/AcpUiEmbed.test.tsx`
- `apps/web/src/shell/acp/__tests__/acpEvents.test.ts`
- `apps/web/README.md`

## Step-by-step implementation checklist

- [x] Add URL construction helper for `VITE_ACP_UI_URL`, carrying `sessionId`, `taskId`, `apiBase`, and a future `acpWsUrl` query parameter.
- [x] Add `AcpUiEmbed` component that renders a full-height iframe and leaves local interaction callbacks untouched.
- [x] Switch `ConversationPane` to render the external iframe only when `VITE_ACP_UI_URL` is configured; otherwise keep `AcpInteractionSurface`.
- [x] Filter known OpenHands housekeeping event types out of ACP updates at the runtime-adapter boundary.
- [x] Stop rendering raw JSON payloads for unknown fallback events in the local surface.
- [x] Add focused frontend tests for iframe URL construction and fallback behavior.
- [x] Add focused OpenHands adapter tests proving housekeeping is skipped but message/file/error events remain.
- [x] Update README with the external ACP UI toggle and the expected local acp-ui serving model.
- [x] Add a minimal `/sessions/{session_id}/acp/ws` JSON-RPC gateway for `initialize`, `session/new`, `session/prompt`, `session/cancel`, and `session/update` notifications.

## Verification commands

```powershell
python -m pytest agent/runtime-adapters/openhands/tests/test_openhands_adapter.py -q
cd apps/web; npm run test:unit -- src/shell/acp/__tests__/AcpUiEmbed.test.tsx src/shell/acp/__tests__/AcpInteractionSurface.test.tsx src/shell/acp/__tests__/acpEvents.test.ts
cd apps/web; npm run test
Get-ChildItem -Recurse -File | Select-Object FullName
```

## Rollback or recovery notes

- Unset `VITE_ACP_UI_URL` to return immediately to the local DocAgent ACP surface.
- The OpenHands raw runtime audit log is still preserved separately; this only suppresses housekeeping from the user-facing ACP update stream.

## Open questions

- Which upstream `acp-ui` fork or pinned commit should become the long-lived embedded client?
- Should the direct `services/api` gateway remain the permanent implementation, or move behind a sidecar if deployments need protocol isolation later?
