from pathlib import Path

from docagent_contracts import (
    AcpRuntimeAdapter,
    AcpRuntimeUpdate,
    PromptBundle,
    RawRuntimeEvent,
    RuntimeAdapter,
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


def test_prompt_bundle_can_identify_pack_management_owner(tmp_path: Path) -> None:
    bundle = PromptBundle(
        system_prompt="system",
        task_instruction="task",
        workspace_root=tmp_path,
        doc_type_id="",
        pack_id="memo",
        metadata={"session_scope": "pack-management"},
    )

    assert bundle.pack_id == "memo"
    assert bundle.doc_type_id == ""


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


def test_runtime_adapter_contract_is_acp_only() -> None:
    assert RuntimeAdapter is AcpRuntimeAdapter
