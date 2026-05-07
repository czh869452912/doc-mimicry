from __future__ import annotations

from docagent_contracts import RuntimeSessionState


class InvalidSessionTransition(ValueError):
    pass


ALLOWED_TRANSITIONS: dict[RuntimeSessionState, set[RuntimeSessionState]] = {
    RuntimeSessionState.IDLE: {
        RuntimeSessionState.RUNNING_CONTEXT,
        RuntimeSessionState.RUNNING_REVISION,
        RuntimeSessionState.RUNNING_CHAT,
        RuntimeSessionState.CANCELLED,
    },
    RuntimeSessionState.RUNNING_CONTEXT: {
        RuntimeSessionState.AWAIT_OUTLINE_APPROVAL,
        RuntimeSessionState.FAILED,
        RuntimeSessionState.CANCELLED,
    },
    RuntimeSessionState.AWAIT_OUTLINE_APPROVAL: {
        RuntimeSessionState.RUNNING_DRAFT,
        RuntimeSessionState.CANCELLED,
    },
    RuntimeSessionState.RUNNING_DRAFT: {
        RuntimeSessionState.DRAFT_READY,
        RuntimeSessionState.FAILED,
        RuntimeSessionState.CANCELLED,
    },
    RuntimeSessionState.DRAFT_READY: {
        RuntimeSessionState.RUNNING_REVISION,
        RuntimeSessionState.RUNNING_CHAT,
        RuntimeSessionState.RUNNING_CHECKLIST,
        RuntimeSessionState.RUNNING_EXPORT,
        RuntimeSessionState.COMPLETED,
        RuntimeSessionState.CANCELLED,
    },
    RuntimeSessionState.RUNNING_REVISION: {
        RuntimeSessionState.DRAFT_READY,
        RuntimeSessionState.FAILED,
        RuntimeSessionState.CANCELLED,
    },
    RuntimeSessionState.RUNNING_CHAT: {
        RuntimeSessionState.DRAFT_READY,
        RuntimeSessionState.FAILED,
        RuntimeSessionState.CANCELLED,
    },
    RuntimeSessionState.RUNNING_CHECKLIST: {
        RuntimeSessionState.DRAFT_READY,
        RuntimeSessionState.FAILED,
        RuntimeSessionState.CANCELLED,
    },
    RuntimeSessionState.RUNNING_EXPORT: {
        RuntimeSessionState.DRAFT_READY,
        RuntimeSessionState.COMPLETED,
        RuntimeSessionState.FAILED,
        RuntimeSessionState.CANCELLED,
    },
    RuntimeSessionState.PAUSED: {
        RuntimeSessionState.RUNNING_CONTEXT,
        RuntimeSessionState.RUNNING_DRAFT,
        RuntimeSessionState.RUNNING_REVISION,
        RuntimeSessionState.CANCELLED,
    },
    RuntimeSessionState.FAILED: {
        RuntimeSessionState.RUNNING_CONTEXT,
        RuntimeSessionState.RUNNING_DRAFT,
        RuntimeSessionState.RUNNING_REVISION,
        RuntimeSessionState.RUNNING_CHAT,
        RuntimeSessionState.CANCELLED,
    },
    RuntimeSessionState.CANCELLED: set(),
    RuntimeSessionState.COMPLETED: set(),
}


def parse_state(value: str | RuntimeSessionState) -> RuntimeSessionState:
    if isinstance(value, RuntimeSessionState):
        return value
    return RuntimeSessionState(value)


def require_transition(
    current: str | RuntimeSessionState,
    next_state: RuntimeSessionState,
) -> RuntimeSessionState:
    current_state = parse_state(current)
    if current_state == next_state:
        return next_state
    if next_state not in ALLOWED_TRANSITIONS[current_state]:
        raise InvalidSessionTransition(f"Cannot transition session from {current_state.value} to {next_state.value}")
    return next_state
