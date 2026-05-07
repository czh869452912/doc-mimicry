from docagent_contracts import RawRuntimeEvent, RuntimeKind, SemanticEventKind
from docagent_timeline import map_openhands_raw_event


def _raw(id: str, kind: str, payload: dict) -> RawRuntimeEvent:
    return RawRuntimeEvent(
        id=id,
        session_id="session-001",
        runtime=RuntimeKind.OPENHANDS,
        runtime_session_id="openhands-001",
        kind=kind,
        payload=payload,
        created_at="2026-05-06T00:00:00Z",
    )


def test_maps_openhands_outline_path_to_propose_outline() -> None:
    event = map_openhands_raw_event(_raw("raw-001", "file_written", {"path": "draft/outline.md"}), task_id="task-001")

    assert event is not None
    assert event.kind is SemanticEventKind.PROPOSE_OUTLINE
    assert event.raw_event_id == "raw-001"


def test_maps_openhands_artifact_path_to_export_markdown() -> None:
    event = map_openhands_raw_event(_raw("raw-002", "file_written", {"path": "artifacts/prd-draft.md"}), task_id="task-001")

    assert event is not None
    assert event.kind is SemanticEventKind.EXPORT_MARKDOWN


def test_skips_session_created_event() -> None:
    event = map_openhands_raw_event(
        _raw("raw-003", "session_created", {"workspace_root": "/some/path", "doc_type_id": "prd"}),
        task_id="task-001",
    )

    assert event is None


def test_skips_system_prompt_event() -> None:
    event = map_openhands_raw_event(_raw("raw-004", "SystemPromptEvent", {"system_prompt": "..."}), task_id="task-001")

    assert event is None


def test_skips_conversation_state_update_event() -> None:
    event = map_openhands_raw_event(
        _raw("raw-005", "ConversationStateUpdateEvent", {"key": "execution_status", "value": "running"}),
        task_id="task-001",
    )

    assert event is None


def test_skips_message_event_with_empty_content() -> None:
    event = map_openhands_raw_event(
        _raw("raw-006", "MessageEvent", {"source": "agent", "llm_message": {"role": "assistant", "content": []}}),
        task_id="task-001",
    )

    assert event is None


def test_agent_message_event_with_text_content() -> None:
    event = map_openhands_raw_event(
        _raw("raw-009", "MessageEvent", {
            "source": "agent",
            "llm_message": {"role": "assistant", "content": [{"type": "text", "text": "Here is the outline."}]},
        }),
        task_id="task-001",
    )

    assert event is not None
    assert event.kind is SemanticEventKind.AGENT_MESSAGE
    assert event.summary == "Here is the outline."


def test_skips_user_message_event() -> None:
    event = map_openhands_raw_event(
        _raw("raw-010", "MessageEvent", {"source": "user", "llm_message": {"role": "user", "content": [{"type": "text", "text": "hi"}]}}),
        task_id="task-001",
    )

    assert event is None


def test_skips_unknown_path() -> None:
    event = map_openhands_raw_event(_raw("raw-007", "file_written", {"path": "some/unknown/file.md"}), task_id="task-001")

    assert event is None


def test_cancelled_maps_to_error() -> None:
    event = map_openhands_raw_event(_raw("raw-008", "cancelled", {}), task_id="task-001")

    assert event is not None
    assert event.kind is SemanticEventKind.ERROR
