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

CI covers the OpenHands boundary with fake-client adapter contract tests. Those
tests verify prompt-bundle forwarding, generic document-type metadata, ACP event
mapping, and error projection without requiring live provider credentials. Live
OpenHands smoke remains opt-in through `tools/runtime/openhands_smoke.py` and
can be pointed at a second document type with `--doc-type`.

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

Runtime sessions are scoped. Authoring sessions use
`session_scope = authoring`, a task workspace, and skill guidance resolved from
the task's immutable published `pack_version_id` when available. Skill Creator
sessions use `session_scope = pack-management`, a draft skill-pack workspace,
and management ACP events stored separately from authoring timelines. Background
authoring workers must reject pack-management sessions instead of treating them
as task sessions.

## Runtime-Agnostic Expectations

The rest of the product should reason about:

- task id
- session id
- session scope
- workspace paths
- ACP events
- semantic projections
- approvals
- artifacts

It should not depend on a specific runtime event payload outside the adapter or
ACP shim. Semantic timeline events are projections, not the runtime contract.

