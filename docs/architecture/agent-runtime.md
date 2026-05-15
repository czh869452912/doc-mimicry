# Agent Runtime

The runtime should provide a Claude Code-like loop for documents.

## Required Capabilities

- Free-form conversation.
- File read/write/edit tools.
- Optional shell with strict controls.
- Event stream.
- Sandbox per task.
- User interrupt.
- Session resume.
- Context management or condenser.
- Configurable system prompt and document type skill guidance.

## Formal Contract

ACP is the only formal session and timeline protocol between DocAgent and agent
runtimes. DocAgent owns the ACP gateway, durable ACP event log, and product
projections for workspace, approvals, artifacts, and audit. The center timeline
reads ACP events from the backend-owned event log.

LiteLLM Proxy is the formal model gateway for provider-backed runtimes. Runtime
adapters select LiteLLM model aliases instead of configuring provider endpoints
directly.

See `docs/decisions/2026-05-14-acp-interaction-plane-and-litellm-gateway.md`.

## Runtime Candidate

OpenHands Agent Server / SDK is the first runtime candidate because it already
exposes many coding-agent primitives. It is connected through the ACP adapter
boundary, not as a UI-facing protocol.

Runtime selection uses `DOCAGENT_RUNTIME=mock-acp` for local/CI mock behavior
and `DOCAGENT_RUNTIME=openhands-acp` for OpenHands. The OpenHands adapter reads
`DOCAGENT_ACP_RUNTIME_URL`; `OPENHANDS_BASE_URL` is only a temporary
compatibility fallback for the current SDK client.

## Adapter Boundary

The backend calls a runtime adapter, not the runtime directly. Supported
adapters expose the ACP session surface:

Formal adapter operations:

```text
create_session(session_id, prompt_bundle)
send_prompt(session_id, prompt, metadata)
stream_updates(session_id)
cancel(session_id)
```

Document actions such as start loop, approve outline, revise selection, run
checklist, and export are prompts with metadata and product-owned expected
states. They are not runtime adapter methods. Any runtime-specific implementation
must adapt to the ACP surface before product state or UI timeline consumption.

## Runtime-Agnostic Expectations

The rest of the product should reason about:

- task id
- session id
- workspace paths
- ACP events
- semantic projections
- approvals
- artifacts

It should not depend on a specific runtime event payload outside the adapter or
ACP shim. Semantic timeline events are projections, not the runtime contract.

