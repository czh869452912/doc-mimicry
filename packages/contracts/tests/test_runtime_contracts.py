from pathlib import Path

from docagent_contracts import (
    PromptBundle,
    RawRuntimeEvent,
    RuntimeEventSink,
    RuntimeKind,
    RuntimeOperationResult,
    RuntimeSessionState,
    StreamingRuntimeAdapter,
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


def test_streaming_runtime_adapter_protocol_is_importable() -> None:
    assert StreamingRuntimeAdapter is not None
