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

## First Candidate

OpenHands Agent Server / SDK is the first candidate because it already exposes many coding-agent primitives.

## Current Direction

Agent interaction uses ACP as the canonical session and timeline protocol.
DocAgent owns an ACP gateway, durable ACP event log, and product projections for
workspace, approvals, artifacts, and audit. The center timeline renders ACP
events directly where possible, while DocAgent-specific cards are derived
projections.

LiteLLM Proxy should be used as the model gateway for real runtimes so provider compatibility, routing, fallback, and credentials are not spread across runtime adapters.

See `docs/decisions/2026-05-14-acp-interaction-plane-and-litellm-gateway.md`.

## Adapter Boundary

The backend should call a runtime adapter, not the runtime directly. ACP-capable
adapters should expose this surface:

Expected adapter operations:

```text
create_session(session_id, prompt_bundle)
send_prompt(session_id, prompt, metadata)
stream_updates(session_id)
cancel(session_id)
```

Older operation-specific methods such as `start_loop`, `approve_outline`, and
their streaming variants are compatibility fallbacks for legacy adapters. New
runtime integrations should not add more operation-specific methods; product
actions are ACP prompts with metadata and product-owned expected states.

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
ACP shim. Semantic timeline events are projections, not the primary runtime
contract.

