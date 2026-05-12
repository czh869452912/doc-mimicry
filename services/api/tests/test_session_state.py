import pytest

from docagent_api.session_state import InvalidSessionTransition, require_transition
from docagent_contracts import RuntimeSessionState


def test_require_transition_allows_known_path() -> None:
    assert (
        require_transition("idle", RuntimeSessionState.RUNNING_CONTEXT)
        == RuntimeSessionState.RUNNING_CONTEXT
    )


def test_require_transition_rejects_invalid_path() -> None:
    with pytest.raises(InvalidSessionTransition, match="Cannot transition"):
        require_transition("idle", RuntimeSessionState.DRAFT_READY)


def test_paused_allows_running_chat() -> None:
    assert (
        require_transition("paused", RuntimeSessionState.RUNNING_CHAT)
        == RuntimeSessionState.RUNNING_CHAT
    )


@pytest.mark.parametrize("status", ["idle", "await_outline_approval"])
def test_chat_is_allowed_from_non_terminal_waiting_states(status: str) -> None:
    assert require_transition(status, RuntimeSessionState.RUNNING_CHAT) == RuntimeSessionState.RUNNING_CHAT
