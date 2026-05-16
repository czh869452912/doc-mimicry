from pathlib import Path
from typing import Any

import pytest

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

    def answer_permission(self, runtime_session_id: str, request_id: str, decision: str) -> list[dict[str, Any]]:
        return [{"kind": "permission_resolved", "request_id": request_id, "decision": decision}]


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
    started = adapter.send_prompt("session-001", "Build context", {"action": "start_loop"})

    assert created.next_state == RuntimeSessionState.IDLE
    assert created.raw_events == []
    assert client.create_calls == 1
    assert started.next_state == RuntimeSessionState.AWAIT_OUTLINE_APPROVAL
    assert started.raw_events[0].kind == "session_created"
    assert started.acp_updates[0].payload["path"] == "draft/outline.md"
    assert started.changed_paths == ["draft/outline.md"]


def test_openhands_adapter_defers_runtime_session_until_first_operation(tmp_path: Path) -> None:
    client = FakeOpenHandsClient()
    adapter = OpenHandsRuntimeAdapter(client)

    result = adapter.create_session("session-001", _prompt_bundle(tmp_path))

    assert result.next_state == RuntimeSessionState.IDLE
    assert result.raw_events == []
    assert client.create_calls == 0

    adapter.send_prompt("session-001", "Build context", {"action": "start_loop"})

    assert client.create_calls == 1


def test_openhands_adapter_cancel_sets_cancelled(tmp_path: Path) -> None:
    adapter = OpenHandsRuntimeAdapter(FakeOpenHandsClient())
    adapter.create_session("session-001", _prompt_bundle(tmp_path))

    result = adapter.cancel("session-001")

    assert result.next_state == RuntimeSessionState.CANCELLED
    assert adapter.get_state("session-001") == RuntimeSessionState.CANCELLED


def test_openhands_adapter_forwards_permission_answers(tmp_path: Path) -> None:
    adapter = OpenHandsRuntimeAdapter(FakeOpenHandsClient())
    adapter.create_session("session-001", _prompt_bundle(tmp_path))
    adapter.send_prompt("session-001", "Build context", {"action": "start_loop"})

    result = adapter.answer_permission("session-001", "permission-1", "allow")

    assert result.next_state == RuntimeSessionState.AWAIT_OUTLINE_APPROVAL
    assert result.raw_events[0].payload["request_id"] == "permission-1"
    assert result.raw_events[0].payload["decision"] == "allow"


def test_openhands_adapter_reports_missing_runtime_session() -> None:
    adapter = OpenHandsRuntimeAdapter(FakeOpenHandsClient())

    try:
        adapter.send_prompt("session-001", "Build context", {"action": "start_loop"})
    except RuntimeError as exc:
        assert str(exc) == "OpenHands runtime session is not bound for session-001. Create a new session."
    else:
        raise AssertionError("Expected missing runtime session to fail clearly")


def test_openhands_adapter_uses_persisted_runtime_session_id() -> None:
    client = FakeOpenHandsClient()
    adapter = OpenHandsRuntimeAdapter(client)

    adapter.bind_runtime_session("session-001", "openhands-session-001", RuntimeSessionState.DRAFT_READY)
    result = adapter.send_prompt("session-001", "Revise", {"action": "send_message"})

    assert result.next_state == RuntimeSessionState.DRAFT_READY
    assert result.raw_events == []
    assert result.acp_updates[0].payload["path"] == "draft/outline.md"
    assert client.messages == ["Revise"]


def test_openhands_adapter_refuses_to_bind_missing_in_process_conversation() -> None:
    class NonResumableClient(FakeOpenHandsClient):
        def has_conversation(self, runtime_session_id: str) -> bool:
            return False

    adapter = OpenHandsRuntimeAdapter(NonResumableClient())

    assert adapter.bind_runtime_session(
        "session-001",
        "openhands-session-001",
        RuntimeSessionState.DRAFT_READY,
    ) is False

    with pytest.raises(RuntimeError, match="not bound"):
        adapter.send_prompt("session-001", "Revise", {"action": "send_message"})


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
        "file/write",
    ]
    assert result.acp_updates[0].projection["timeline_kind"] == "update_draft"


def test_send_prompt_returns_acp_updates_and_preserves_raw_payload(tmp_path: Path) -> None:
    client = MixedPayloadOpenHandsClient()
    adapter = OpenHandsRuntimeAdapter(client)
    adapter.create_session("session-001", _prompt_bundle(tmp_path))

    result = adapter.send_prompt("session-001", "Write", {"action": "send_message"})

    assert [update.event_type for update in result.acp_updates] == [
        "message_delta",
        "file/write",
        "openhands/strange_event",
    ]
    assert result.acp_updates[-1].payload["value"] == 42


def test_openhands_adapter_preserves_payloads_in_acp_updates_from_prompt_result(tmp_path: Path) -> None:
    adapter = OpenHandsRuntimeAdapter(FakeOpenHandsClient())
    adapter.create_session("session-001", _prompt_bundle(tmp_path))

    result = adapter.send_prompt("session-001", "Revise", {"action": "send_message"})

    assert result.next_state == RuntimeSessionState.DRAFT_READY
    assert result.raw_events[0].kind == "session_created"
    assert result.acp_updates[0].payload["path"] == "draft/outline.md"
    assert result.changed_paths == ["draft/outline.md"]


def test_openhands_payload_maps_to_acp_update() -> None:
    update = map_openhands_payload_to_acp_update(
        "session-001",
        {"kind": "file_written", "path": "draft/draft.md"},
    )

    assert update is not None
    assert update.event_type == "file/write"
    assert update.payload["path"] == "draft/draft.md"
    assert update.projection["timeline_kind"] == "update_draft"


def test_openhands_message_event_maps_to_message_delta() -> None:
    update = map_openhands_payload_to_acp_update(
        "session-001",
        {
            "kind": "MessageEvent",
            "source": "agent",
            "llm_message": {"content": [{"type": "text", "text": "Here is the outline."}]},
        },
    )

    assert update is not None
    assert update.event_type == "message_delta"
    assert update.payload["content"] == "Here is the outline."


def test_openhands_action_event_maps_to_file_or_tool_update() -> None:
    file_update = map_openhands_payload_to_acp_update(
        "session-001",
        {
            "kind": "ActionEvent",
            "action": {"kind": "FileEditorAction", "path": "draft/draft.md"},
        },
    )
    tool_update = map_openhands_payload_to_acp_update(
        "session-001",
        {
            "kind": "ActionEvent",
            "action": {"kind": "TaskTrackerAction", "command": "plan", "task_list": [{"title": "Draft"}]},
        },
    )

    assert file_update is not None
    assert file_update.event_type == "file/write"
    assert file_update.payload["path"] == "draft/draft.md"
    assert tool_update is not None
    assert tool_update.event_type == "tool/call"
    assert tool_update.projection["summary"] == "Updating task list (1 tasks)"


def test_openhands_housekeeping_payloads_do_not_emit_acp_updates() -> None:
    for payload in [
        {"kind": "session_created", "workspace_root": "/workspace/task-1"},
        {"kind": "ConversationStateUpdateEvent", "key": "execution_status", "value": "running"},
        {"kind": "SystemPromptEvent", "system_prompt": "..."},
        {"kind": "ObservationEvent", "path": "draft/draft.md"},
    ]:
        assert map_openhands_payload_to_acp_update("session-001", payload) is None


def test_openhands_error_payload_maps_to_failed_acp_update() -> None:
    update = map_openhands_payload_to_acp_update(
        "session-001",
        {
            "kind": "ConversationErrorEvent",
            "code": "APIError",
            "detail": "provider connection failed",
        },
    )

    assert update is not None
    assert update.event_type == "runtime/error"
    assert update.projection["status"] == "failed"
    assert "APIError" in update.projection["summary"]


def _prompt_bundle(workspace: Path) -> PromptBundle:
    return PromptBundle(
        system_prompt="system",
        task_instruction="task",
        workspace_root=workspace,
        doc_type_id="prd",
        metadata={"task_id": "task-001"},
    )
