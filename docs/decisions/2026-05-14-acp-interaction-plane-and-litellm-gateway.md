# ACP Interaction Plane And LiteLLM Gateway

## Context

DocAgent Workbench needs a document-version coding-agent experience: free conversation, streaming progress, user interruption, tool visibility, session resume, workspace edits, approvals, and audit.

The current implementation has separate boundaries for runtime adapter calls, raw runtime events, semantic timeline events, Server-Sent Events, and assistant UI messages. That has made the full agent-to-UI chain expensive to maintain. Adding each runtime operation requires more adapter methods, streaming variants, mapper logic, UI rendering states, and tests. The timeline also loses information because runtime payloads are compressed into small semantic summaries before the center timeline can render them.

The model-provider boundary has a different problem. Runtime code currently reads model, base URL, and API key settings directly. That pushes provider compatibility, fallback, routing, and key handling into runtime configuration rather than a dedicated model gateway.

## Decision

DocAgent will use Agent Client Protocol as the canonical interaction contract for agent sessions and center timeline rendering.

ACP is the source of truth for agent-visible interaction events:

- session creation and loading
- user prompts
- streaming agent messages
- tool calls and tool results
- file and command activity
- permission or approval requests
- cancellation, failure, and resume state

DocAgent will keep product ownership around ACP rather than exposing runtimes directly to the UI. The backend remains responsible for task state, workspace contracts, document type packs, versions, artifacts, approvals, audit, and durable event storage.

The center timeline will render ACP events directly where possible. DocAgent-specific cards are projections from ACP events, not the primary event source. Examples:

- a draft outline write projects to an outline review card
- a draft write projects to a draft update card
- a checklist result write projects to a checklist card
- an artifact write projects to an artifact card
- an ACP permission request projects to a DocAgent approval card

The existing operation-specific runtime adapter surface will be retired in favor of a small ACP session surface. Product actions such as start loop, approve outline, revise selection, run checklist, and export become prompts or commands with metadata and expected workspace outcomes, not runtime adapter methods.

DocAgent will also add LiteLLM Proxy as the model gateway. Agent runtimes should call models through LiteLLM aliases instead of configuring every model provider directly in each runtime adapter.

## Consequences

- The raw ACP event log becomes the durable interaction record and timeline source of truth.
- Semantic DocAgent events become rebuildable projections used for product cards, workspace invalidation, and reporting.
- Runtime backends become replaceable when they are ACP-native or can be wrapped by an ACP shim.
- The UI no longer needs a custom event protocol for every runtime-specific behavior.
- OpenHands remains useful as an initial runtime, but it should be connected through an ACP shim or replaced by an ACP-native runtime when practical.
- LiteLLM centralizes provider compatibility, routing, fallback, budget, and key management.
- The product must define a migration path that preserves current authoring behavior while moving the interaction chain to ACP.
- LiteLLM must be pinned and operated as infrastructure. Security advisories and upgrade discipline matter because the proxy handles model credentials and traffic.

## Alternatives Considered

- Keep the current runtime adapter contract and keep patching event mappers. Rejected because it keeps the most expensive part of the system custom: the agent interaction protocol.
- Use ACP only behind the runtime adapter while keeping the UI on custom semantic timeline events. Rejected because it would leave the center timeline boundary unsolved and preserve most UI-agent debugging cost.
- Let the UI connect directly to each runtime's ACP endpoint. Rejected because it bypasses DocAgent product state, workspace contracts, approvals, artifacts, and audit.
- Use LiteLLM as a replacement for ACP. Rejected because LiteLLM is a model gateway, not an agent-client interaction protocol.
