from pathlib import Path

from docagent_contracts import (
    AcpRuntimeAdapter,
    AcpRuntimeUpdate,
    LegacyRuntimeAdapter,
    PromptBundle,
    RawRuntimeEvent,
    RuntimeEventSink,
    RuntimeKind,
    RuntimeOperationResult,
    RuntimeSessionState,
    utc_now,
)


def test_prompt_bundle_defaults_metadata() -> None:
    bundle = PromptBundle(
        system_prompt="system",
        task_instruction="task",
        workspace_root=Path("/workspace"),
        doc_type_id="prd",
    )

    assert bundle.metadata == {}


def test_runtime_operation_result_defaults() -> None:
    result = RuntimeOperationResult(
        session_id="session-1",
        next_state=RuntimeSessionState.AWAIT_OUTLINE_APPROVAL,
    )

    assert result.events == []
    assert result.changed_paths == []
    assert result.raw_events == []


def test_raw_runtime_event_captures_runtime_identity() -> None:
    event = RawRuntimeEvent(
        id="raw-1",
        session_id="session-1",
        runtime=RuntimeKind.OPENHANDS,
        runtime_session_id="openhands-1",
        kind="file_written",
        payload={"path": "draft.md"},
        created_at=utc_now(),
    )

    assert event.runtime == RuntimeKind.OPENHANDS
    assert event.payload["path"] == "draft.md"
    assert event.created_at.endswith("Z")


def test_runtime_event_sink_receives_raw_event() -> None:
    received: list[RawRuntimeEvent] = []

    def sink(event: RawRuntimeEvent) -> None:
        received.append(event)

    event = RawRuntimeEvent(
        id="raw-2",
        session_id="session-1",
        runtime=RuntimeKind.OPENHANDS,
        runtime_session_id="openhands-1",
        kind="message",
        payload={"content": "hello"},
        created_at=utc_now(),
    )

    typed_sink: RuntimeEventSink = sink
    typed_sink(event)

    assert received == [event]


def test_running_chat_state_exists() -> None:
    from docagent_contracts import RuntimeSessionState
    assert RuntimeSessionState.RUNNING_CHAT.value == "running_chat"


def test_acp_runtime_update_shape() -> None:
    update = AcpRuntimeUpdate(
        session_id="session-1",
        event_type="message_delta",
        payload={"role": "assistant", "content": "Hello"},
        projection={"timeline_kind": "agent_message"},
    )

    assert update.session_id == "session-1"
    assert update.event_type == "message_delta"
    assert update.payload["content"] == "Hello"
    assert update.projection == {"timeline_kind": "agent_message"}


def test_acp_runtime_adapter_protocol_is_importable() -> None:
    assert AcpRuntimeAdapter is not None


def test_acp_runtime_adapter_protocol_includes_permission_response() -> None:
    assert "answer_permission" in AcpRuntimeAdapter.__dict__


def test_legacy_runtime_adapter_protocol_is_importable_for_compatibility() -> None:
    assert LegacyRuntimeAdapter is not None
