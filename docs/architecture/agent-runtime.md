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

Agent interaction should converge on ACP as the canonical session and timeline protocol. DocAgent should own an ACP gateway, durable ACP event log, and product projections for workspace, approvals, artifacts, and audit. The center timeline should render ACP events directly where possible, while DocAgent-specific cards are derived projections.

LiteLLM Proxy should be used as the model gateway for real runtimes so provider compatibility, routing, fallback, and credentials are not spread across runtime adapters.

See `docs/decisions/2026-05-14-acp-interaction-plane-and-litellm-gateway.md` and `docs/exec-plans/active/2026-05-14-acp-litellm-migration.md`.

## Adapter Boundary

The backend should call a runtime adapter, not the runtime directly.

Expected adapter operations:

```text
create_session(task_id, workspace_config)
send_message(session_id, message)
stream_events(session_id)
pause(session_id)
resume(session_id)
cancel(session_id)
approve_action(session_id, action_id)
reject_action(session_id, action_id)
get_state(session_id)
```

## Runtime-Agnostic Expectations

The rest of the product should reason about:

- task id
- session id
- workspace paths
- semantic events
- approvals
- artifacts

It should not depend on a specific runtime event payload outside the adapter and timeline mapper.

