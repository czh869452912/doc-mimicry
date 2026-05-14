# ACP Interaction Plane And LiteLLM Gateway

Status: accepted, canonical.

## Context

DocAgent Workbench needs a document-version coding-agent experience: free conversation, streaming progress, user interruption, tool visibility, session resume, workspace edits, approvals, and audit.

Before this decision, the implementation had separate boundaries for runtime adapter calls, raw runtime events, semantic timeline events, Server-Sent Events, and assistant UI messages. That made the full agent-to-UI chain expensive to maintain. Adding each runtime operation required more adapter methods, streaming variants, mapper logic, UI rendering states, and tests. The timeline also lost information because runtime payloads were compressed into small semantic summaries before the center timeline could render them.

The model-provider boundary had a different problem. Runtime code read model, base URL, and API key settings directly. That pushed provider compatibility, routing, fallback, and key handling into runtime configuration rather than a dedicated model gateway.

## Decision

DocAgent uses Agent Client Protocol as the only formal interaction contract for agent sessions and center timeline rendering.

ACP is the source of truth for agent-visible interaction events:

- session creation and loading
- user prompts
- streaming agent messages
- tool calls and tool results
- file and command activity
- permission or approval requests
- cancellation, failure, and resume state

DocAgent will keep product ownership around ACP rather than exposing runtimes directly to the UI. The backend remains responsible for task state, workspace contracts, document type packs, versions, artifacts, approvals, audit, and durable event storage.

The center timeline reads the DocAgent-owned ACP event log. DocAgent-specific cards are projections from ACP events, not a second timeline protocol. Examples:

- a draft outline write projects to an outline review card
- a draft write projects to a draft update card
- a checklist result write projects to a checklist card
- an artifact write projects to an artifact card
- an ACP permission request projects to a DocAgent approval card

The operation-specific runtime adapter surface is retired as a product contract. Product actions such as start loop, approve outline, revise selection, run checklist, and export are ACP prompts or commands with metadata and expected workspace outcomes, not runtime adapter methods.

DocAgent uses LiteLLM Proxy as the formal model gateway for provider-backed runtime traffic. Agent runtimes call models through LiteLLM aliases instead of configuring provider endpoints directly in each runtime adapter.

## Contract Rules

- Backend-to-runtime interaction uses the ACP session surface: create or load session, send prompt, stream updates, cancel, and inspect state.
- Runtime-to-backend updates are stored as ACP event envelopes before they are exposed to UI or product projections.
- Backend-to-UI timeline streaming uses `/sessions/{session_id}/events` and `/sessions/{session_id}/events/stream`.
- Semantic timeline events are derived read models for cards, invalidation, and reports. They are not the authoring timeline contract.
- Runtime-specific payloads may exist only inside an ACP-native runtime, an ACP shim, or raw audit fields attached to ACP events.
- New runtime integrations must not add product-specific adapter methods for document actions.
- Provider-backed model calls go through LiteLLM model aliases. Direct provider endpoints are not the supported product contract.

## Consequences

- The raw ACP event log becomes the durable interaction record and timeline source of truth.
- Semantic DocAgent events become rebuildable projections used for product cards, workspace invalidation, and reporting.
- Runtime backends become replaceable when they are ACP-native or can be wrapped by an ACP shim.
- The UI no longer owns a custom event protocol for runtime-specific behavior.
- OpenHands remains useful as an initial runtime, but it should be connected through an ACP shim or replaced by an ACP-native runtime when practical.
- LiteLLM centralizes provider compatibility, routing, fallback, budget, and key management.
- Any remaining non-ACP implementation code is internal adapter machinery that must emit ACP events before product/UI consumption.
- LiteLLM must be pinned and operated as infrastructure. Security advisories and upgrade discipline matter because the proxy handles model credentials and traffic.

## Alternatives Considered

- Keep the current runtime adapter contract and keep patching event mappers. Rejected because it keeps the most expensive part of the system custom: the agent interaction protocol.
- Use ACP only behind the runtime adapter while keeping the UI on custom semantic timeline events. Rejected because it would leave the center timeline boundary unsolved and preserve most UI-agent debugging cost.
- Let the UI connect directly to each runtime's ACP endpoint. Rejected because it bypasses DocAgent product state, workspace contracts, approvals, artifacts, and audit.
- Use LiteLLM as a replacement for ACP. Rejected because LiteLLM is a model gateway, not an agent-client interaction protocol.
