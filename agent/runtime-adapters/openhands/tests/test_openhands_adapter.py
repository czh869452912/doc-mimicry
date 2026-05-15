from pathlib import Path
from typing import Any

from docagent_contracts import PromptBundle, RuntimeSessionState
from docagent_openhands_runtime.adapter import OpenHandsRuntimeAdapter, map_openhands_payload_to_acp_update


class FakeOpenHandsClient:
    def __init__(self) -> None:
        self.messages: list[str] = []
        self.create_calls = 0

    def create_session(self, prompt_bundle: PromptBundle) -> str:
        self.create_calls += 1
        return "openhands-session-001"

    def send_message(self, runtime_session_id: str, message: str) -> list[dict[str, Any]]:
        self.messages.append(message)
        return [{"kind": "file_written", "path": "draft/outline.md"}]

    def send_message_stream(self, runtime_session_id: str, message: str) -> Any:
        self.messages.append(message)
        yield {"kind": "file_written", "path": "draft/streamed.md"}

    def cancel_session(self, runtime_session_id: str) -> list[dict[str, Any]]:
        return [{"kind": "cancelled"}]


class MixedPayloadOpenHandsClient(FakeOpenHandsClient):
    def send_message(self, runtime_session_id: str, message: str) -> list[dict[str, Any]]:
        self.messages.append(message)
        return [
            {"kind": "agent_message", "id": "m1", "content": "Hello"},
            {"kind": "file_written", "path": "draft/draft.md", "content": "Draft"},
            {"kind": "strange_event", "value": 42},
        ]


def test_openhands_adapter_creates_session_and_maps_raw_events(tmp_path: Path) -> None:
    client = FakeOpenHandsClient()
    adapter = OpenHandsRuntimeAdapter(client)

    created = adapter.create_session("session-001", _prompt_bundle(tmp_path))
    started = adapter.start_loop("session-001")

    assert created.next_state == RuntimeSessionState.IDLE
    assert created.raw_events == []
    assert client.create_calls == 1
    assert started.next_state == RuntimeSessionState.AWAIT_OUTLINE_APPROVAL
    assert started.raw_events[0].kind == "session_created"
    assert started.raw_events[1].payload["path"] == "draft/outline.md"
    assert started.changed_paths == ["draft/outline.md"]


def test_openhands_adapter_defers_runtime_session_until_first_operation(tmp_path: Path) -> None:
    client = FakeOpenHandsClient()
    adapter = OpenHandsRuntimeAdapter(client)

    result = adapter.create_session("session-001", _prompt_bundle(tmp_path))

    assert result.next_state == RuntimeSessionState.IDLE
    assert result.raw_events == []
    assert client.create_calls == 0

    adapter.start_loop("session-001")

    assert client.create_calls == 1


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


def test_openhands_adapter_uses_persisted_runtime_session_id() -> None:
    client = FakeOpenHandsClient()
    adapter = OpenHandsRuntimeAdapter(client)

    adapter.bind_runtime_session("session-001", "openhands-session-001", RuntimeSessionState.DRAFT_READY)
    result = adapter.send_message("session-001", "Revise")

    assert result.next_state == RuntimeSessionState.DRAFT_READY
    assert result.raw_events[0].runtime_session_id == "openhands-session-001"
    assert client.messages == ["Revise"]


def test_openhands_adapter_send_prompt_emits_acp_updates(tmp_path: Path) -> None:
    client = FakeOpenHandsClient()
    adapter = OpenHandsRuntimeAdapter(client)
    adapter.create_session("session-001", _prompt_bundle(tmp_path))

    result = adapter.send_prompt(
        "session-001",
        "Revise the draft",
        {"action": "send_message"},
    )

    assert result.next_state == RuntimeSessionState.DRAFT_READY
    assert len(result.raw_events) == 1
    assert result.raw_events[0].kind == "session_created"
    assert client.messages == ["Revise the draft"]
    assert [update.event_type for update in result.acp_updates] == [
        "openhands/session_created",
        "file/write",
    ]
    assert result.acp_updates[1].projection["timeline_kind"] == "update_draft"


def test_send_prompt_returns_acp_updates_and_preserves_raw_payload(tmp_path: Path) -> None:
    client = MixedPayloadOpenHandsClient()
    adapter = OpenHandsRuntimeAdapter(client)
    adapter.create_session("session-001", _prompt_bundle(tmp_path))

    result = adapter.send_prompt("session-001", "Write", {"action": "send_message"})

    assert [update.event_type for update in result.acp_updates] == [
        "openhands/session_created",
        "message_delta",
        "file/write",
        "openhands/strange_event",
    ]
    assert result.acp_updates[-1].payload["value"] == 42


def test_openhands_adapter_streams_raw_events_to_sink(tmp_path: Path) -> None:
    adapter = OpenHandsRuntimeAdapter(FakeOpenHandsClient())
    adapter.create_session("session-001", _prompt_bundle(tmp_path))
    streamed = []

    result = adapter.send_message_stream("session-001", "Revise", streamed.append)

    assert result.next_state == RuntimeSessionState.DRAFT_READY
    assert result.raw_events == []
    assert streamed[0].payload["path"] == "draft/streamed.md"
    assert result.changed_paths == ["draft/streamed.md"]


def test_openhands_payload_maps_to_acp_update() -> None:
    update = map_openhands_payload_to_acp_update(
        "session-001",
        {"kind": "file_written", "path": "draft/draft.md"},
    )

    assert update.event_type == "file/write"
    assert update.payload["path"] == "draft/draft.md"
    assert update.projection["timeline_kind"] == "update_draft"


def _prompt_bundle(workspace: Path) -> PromptBundle:
    return PromptBundle(
        system_prompt="system",
        task_instruction="task",
        workspace_root=workspace,
        doc_type_id="prd",
        metadata={"task_id": "task-001"},
    )
