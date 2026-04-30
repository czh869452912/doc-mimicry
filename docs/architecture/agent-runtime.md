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

