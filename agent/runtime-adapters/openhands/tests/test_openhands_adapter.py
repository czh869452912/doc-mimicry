from pathlib import Path
from typing import Any

from docagent_contracts import PromptBundle, RuntimeSessionState
from docagent_openhands_runtime.adapter import OpenHandsRuntimeAdapter


class FakeOpenHandsClient:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def create_session(self, prompt_bundle: PromptBundle) -> str:
        return "openhands-session-001"

    def send_message(self, runtime_session_id: str, message: str) -> list[dict[str, Any]]:
        self.messages.append(message)
        return [{"kind": "file_written", "path": "draft/outline.md"}]

    def cancel_session(self, runtime_session_id: str) -> list[dict[str, Any]]:
        return [{"kind": "cancelled"}]


def test_openhands_adapter_creates_session_and_maps_raw_events(tmp_path: Path) -> None:
    client = FakeOpenHandsClient()
    adapter = OpenHandsRuntimeAdapter(client)

    created = adapter.create_session("session-001", _prompt_bundle(tmp_path))
    started = adapter.start_loop("session-001")

    assert created.next_state == RuntimeSessionState.IDLE
    assert created.raw_events[0].runtime_session_id == "openhands-session-001"
    assert started.next_state == RuntimeSessionState.AWAIT_OUTLINE_APPROVAL
    assert started.raw_events[0].payload["path"] == "draft/outline.md"
    assert started.changed_paths == ["draft/outline.md"]


def test_openhands_adapter_cancel_sets_cancelled(tmp_path: Path) -> None:
    adapter = OpenHandsRuntimeAdapter(FakeOpenHandsClient())
    adapter.create_session("session-001", _prompt_bundle(tmp_path))

    result = adapter.cancel("session-001")

    assert result.next_state == RuntimeSessionState.CANCELLED
    assert adapter.get_state("session-001") == RuntimeSessionState.CANCELLED


def test_openhands_adapter_reports_missing_runtime_session() -> None:
    adapter = OpenHandsRuntimeAdapter(FakeOpenHandsClient())

    try:
        adapter.start_loop("session-001")
    except RuntimeError as exc:
        assert str(exc) == "OpenHands runtime session is not bound for session-001. Create a new session."
    else:
        raise AssertionError("Expected missing runtime session to fail clearly")


def _prompt_bundle(workspace: Path) -> PromptBundle:
    return PromptBundle(
        system_prompt="system",
        task_instruction="task",
        workspace_root=workspace,
        doc_type_id="prd",
        metadata={"task_id": "task-001"},
    )
