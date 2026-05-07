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
