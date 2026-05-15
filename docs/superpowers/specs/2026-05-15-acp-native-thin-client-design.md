# ACP-Native Thin Client Design

## Status

Proposed for review. This spec captures the accepted direction from the
ACP migration review: DocAgent should become a thin product shell around ACP,
remove its custom interaction projection wherever possible, and keep the UI
replaceable when stronger standard ACP UI components appear.

## Context

DocAgent has already moved toward ACP as the canonical interaction plane, but
the current implementation still carries a second internal presentation chain:
ACP events are stored, projected into DocAgent semantic timeline events, mapped
again into assistant-ui messages, and then rendered through assistant-ui data
parts. That keeps too much of the agent interaction burden inside DocAgent.

OpenHands should be treated as an ACP-capable runtime endpoint rather than as a
runtime whose native events DocAgent must continuously remap. LiteLLM remains
the model gateway. DocAgent should focus on the surrounding product: task
state, workspaces, document type packs, Markdown documents, approvals,
versions, artifacts, audit, and deployment packaging.

Frontend evaluation:

- [ACP UI](https://github.com/formulahendry/acp-ui) is the best current
  reference for ACP-native client behavior and information architecture.
- [AionUi](https://github.com/iOfficeAI/AionUi) is useful as product
  inspiration for office-agent workflows, but it is too complete a product shell
  to adopt as DocAgent's center pane foundation.
- [assistant-ui](https://www.assistant-ui.com/docs/runtimes/custom/overview)
  remains a good general assistant runtime library, but its custom runtime and
  transport model still requires DocAgent-owned state conversion. It should not
  remain the long-term interaction boundary.

OpenHands ACP references:

- [Run OpenHands with ACP](https://docs.openhands.dev/openhands/usage/run-openhands/acp)
- [OpenHands SDK ACP guide](https://docs.openhands.dev/sdk/guides/agent-acp)

## Goals

- Make ACP the direct interaction contract from runtime to backend to center UI.
- Remove custom semantic timeline projection from the core conversation path.
- Keep only product-owned derived state: workspace indexes, approval records,
  artifact metadata, audit views, and invalidation hints.
- Replace assistant-ui as the long-term center-pane runtime boundary with a
  small ACP-native interaction shell.
- Keep the ACP UI layer replaceable so a future standard ACP component kit can
  be swapped in behind a narrow local interface.
- Simplify deployment by treating OpenHands as an ACP runtime service and
  LiteLLM as the model gateway, with fewer model/provider settings in the
  product API and worker.

## Non-Goals

- Do not redesign the whole authoring workbench layout.
- Do not expose the runtime directly to the browser and bypass DocAgent product
  state.
- Do not adopt AionUi as the product shell.
- Do not wait for a perfect ACP UI component library before removing the
  internal projection chain.
- Do not turn product actions into fixed workflow steps or runtime-specific
  adapter methods.
- Do not remove Markdown as the internal document format.

## Architecture

```text
React Workbench
  -> DocAgent ACP Interaction Surface
    -> Backend ACP Session Gateway and Event Log
      -> ACP Runtime Client
        -> OpenHands ACP Runtime or Mock ACP Runtime
          -> Task Workspace
          -> LiteLLM Model Gateway
```

The backend remains between UI and runtime. It owns task/session identity,
workspace contracts, durable event storage, authorization, audit, approvals,
artifacts, and product metadata. The center UI reads the backend-owned ACP event
log and renders ACP events directly.

DocAgent-specific cards remain allowed only as presentation adapters over ACP
events or product-owned read models. They must not become a second authoring
timeline protocol.

## Backend Boundary

The backend should expose a small ACP gateway surface:

- create or load a runtime session for a task
- send an ACP prompt/message with DocAgent metadata
- stream and replay ACP event envelopes with sequence numbers
- cancel or interrupt a session
- answer permission or approval requests
- expose product state derived from workspace files and ACP events

The backend should stop treating semantic timeline events as the center thread
contract. The `/timeline` endpoint can remain temporarily as a compatibility
read endpoint, but new frontend work should consume `/sessions/{id}/events` and
`/sessions/{id}/events/stream`.

Product-owned derived state may still exist. Examples include artifact lists,
draft version lists, approval status, workspace tree invalidation, conversion
warnings, and audit reports. These are not runtime interaction projections.

## Runtime Boundary

OpenHands should be connected through its ACP-facing behavior wherever possible.
DocAgent should avoid OpenHands-specific in-memory conversation bookkeeping and
runtime event remapping. The runtime client should know how to:

- establish or resume an ACP session
- send user prompts and product commands as ACP messages
- receive streaming ACP updates
- preserve unknown ACP payloads
- cancel or interrupt the active session
- forward permission responses

The mock runtime should also speak the same ACP subset, so backend and frontend
tests can switch between mock and OpenHands without changing product code.

## Frontend Boundary

The authoring UI keeps the current three-column workbench shape. The center
pane changes from an assistant-ui thread backed by `TimelineEvent[]` into an
ACP-native interaction surface backed by `AcpEvent[]`.

The local UI port is named `AcpInteractionSurface`. This is a DocAgent-owned
interface, not a third-party API:

```text
AcpInteractionSurface
  inputs:
    session id
    ACP events
    connection and running state
    workspace/product render slots
  actions:
    send message
    cancel or interrupt
    answer approval or permission
    open workspace path
    attach imported context
```

All third-party ACP UI components must sit behind this interface. Until a strong
standard component kit exists, DocAgent implements the surface with local React
components informed by ACP UI. Later, a standard ACP UI kit can replace the
local implementation as long as the interface remains unchanged.

assistant-ui can be removed from the core conversation path after parity exists.
During migration it may remain as a temporary implementation detail, but no new
ACP work should depend on assistant-ui message schemas or data-part contracts.

## UI Component Choice

Decision: build a DocAgent ACP-native thin shell now, using ACP UI as the
primary reference and AionUi as product inspiration only.

Rationale:

- It best matches the goal of shrinking custom projection logic.
- It avoids adopting a large external product shell.
- It preserves the existing DocAgent workbench layout and editor surfaces.
- It gives the project a stable local replacement boundary for future ACP UI
  standards.

Replacement rule: no feature outside the ACP center-pane package should import
or depend on a specific ACP UI kit. The rest of the app talks to
`AcpInteractionSurface` and product APIs only.

## Data Flow

User prompt:

```text
Composer
  -> backend send-message endpoint
  -> ACP client request event stored
  -> ACP runtime message
  -> runtime ACP updates stored
  -> event stream
  -> ACP center renderer
```

Runtime tool or file activity:

```text
ACP update
  -> backend event log
  -> stream to center pane
  -> path-based workspace invalidation
  -> workspace tree, draft preview, versions, or artifacts refresh
```

Approval or permission:

```text
ACP permission request
  -> backend event log
  -> approval card render slot
  -> user decision
  -> backend permission response
  -> runtime continues or stops
```

Unknown ACP event:

```text
ACP payload
  -> durable event log
  -> generic inspectable event row
  -> no lossy semantic compression
```

## Deployment Changes

Deployment should make the ACP boundary explicit:

- OpenHands runs as an ACP runtime service.
- API and worker use an ACP runtime endpoint setting, not a broad set of
  OpenHands internals.
- LiteLLM remains the model gateway and owns provider routing, model aliases,
  fallback, and provider credentials.
- API and worker should not need provider API keys for normal OpenHands runs.
- Mock runtime remains available for CI and local development without provider
  credentials.
- Compose profiles or runtime settings should distinguish `mock-acp` and
  `openhands-acp` clearly.
- Shared workspace volumes must remain mounted where both DocAgent and the
  runtime can access task workspaces.

Suggested configuration direction:

```text
DOCAGENT_RUNTIME=mock-acp | openhands-acp
DOCAGENT_ACP_RUNTIME_URL=http://openhands:8001
LITELLM_BASE_URL=http://litellm:4000
```

Existing `OPENHANDS_*` settings may remain inside the runtime-specific
deployment layer during migration, but they should not be the public DocAgent
runtime contract.

## Migration Shape

1. Introduce the ACP interaction surface in the frontend and route center-pane
   reads through `AcpEvent[]`.
2. Add backend tests that fail when runtime updates bypass ACP event storage or
   when center-thread APIs require semantic timeline events.
3. Make OpenHands connection use the native ACP path or the thinnest possible
   ACP client layer.
4. Move DocAgent cards to ACP render slots and product read models.
5. Remove assistant-ui from the core conversation path after send, stream,
   cancel, reload, attachment, approval, and copy behavior have ACP-native
   equivalents.
6. Deprecate `/timeline` for authoring UI use, keeping it only for compatibility
   or reports until no consumers remain.
7. Simplify Docker Compose, `.env.example`, and dev scripts around the ACP
   runtime endpoint and LiteLLM gateway.

## Testing Strategy

Backend:

- ACP event persistence and replay ordering.
- send, stream, cancel, resume, permission response.
- unknown ACP payload preservation.
- no new product runtime adapter methods for document actions.
- config tests for mock and OpenHands ACP deployment settings.

Frontend:

- ACP event renderer snapshots or component tests for message, tool, file,
  permission, status, and unknown event families.
- product card render-slot tests for outline, checklist, artifact, and approval
  events.
- composer action tests that do not depend on assistant-ui message schemas.
- workspace invalidation tests driven by ACP file/path events.

End-to-end:

- user message reaches the runtime and returns ACP events in the center pane.
- runtime file write refreshes the draft preview or workspace tree.
- approval request can be answered from the UI.
- mock ACP and OpenHands ACP runs share the same frontend contract.

Documentation-only verification for this spec:

```powershell
Get-ChildItem -Recurse -File | Select-Object FullName
```

## Risks And Mitigations

- ACP UI libraries may evolve quickly. Mitigation: isolate all UI-kit code
  behind `AcpInteractionSurface`.
- OpenHands native ACP may expose behavior that differs from the existing shim.
  Mitigation: use contract tests against the mock ACP runtime first, then add
  OpenHands smoke coverage.
- Removing semantic timeline consumers may reveal hidden dependencies in
  invalidation and cards. Mitigation: classify each consumer as interaction
  rendering, product read model, or compatibility before deletion.
- A thin local renderer may initially lack assistant-ui conveniences. Mitigation:
  implement only the required authoring behaviors and keep the surface small.

## Success Criteria

- The center pane consumes ACP events directly and no longer requires
  `TimelineEvent[]` or assistant-ui messages.
- Runtime replacement between mock ACP and OpenHands ACP does not require
  frontend changes.
- Unknown ACP events remain visible and inspectable instead of disappearing into
  semantic summaries.
- Product cards are render slots or read models, not a second interaction
  protocol.
- Deployment exposes an ACP runtime endpoint and LiteLLM model gateway as the
  stable operational contract.
- Future standard ACP UI components can replace the local renderer by
  implementing `AcpInteractionSurface`.
