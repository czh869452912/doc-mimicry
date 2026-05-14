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


def test_maps_absolute_container_workspace_path_to_relative_path() -> None:
    event = map_openhands_raw_event(
        _raw("raw-011", "file_written", {
            "path": "/workspace/state/workspaces/task-001/versions/checkpoint.md",
            "workspace_root": "/workspace/state/workspaces/task-001",
        }),
        task_id="task-001",
    )

    assert event is not None
    assert event.kind is SemanticEventKind.CREATE_CHECKPOINT
    assert event.paths == ["versions/checkpoint.md"]


def test_maps_windows_workspace_path_to_relative_path() -> None:
    event = map_openhands_raw_event(
        _raw("raw-012", "file_written", {
            "file_path": r"D:\Project\doc-mimicry\.local\docagent\workspaces\task-001\draft\draft.md",
            "workspace_root": r"D:\Project\doc-mimicry\.local\docagent\workspaces\task-001",
        }),
        task_id="task-001",
    )

    assert event is not None
    assert event.kind is SemanticEventKind.UPDATE_DRAFT
    assert event.paths == ["draft/draft.md"]


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


def test_task_tracker_view_maps_to_agent_tool_call() -> None:
    event = map_openhands_raw_event(
        _raw("raw-t01", "ActionEvent", {"action": {"kind": "TaskTrackerAction", "command": "view", "task_list": []}}),
        task_id="task-001",
    )

    assert event is not None
    assert event.kind is SemanticEventKind.AGENT_TOOL_CALL
    assert event.summary == "Checking task list"


def test_task_tracker_plan_maps_to_agent_tool_call_with_count() -> None:
    event = map_openhands_raw_event(
        _raw("raw-t02", "ActionEvent", {
            "action": {
                "kind": "TaskTrackerAction",
                "command": "plan",
                "task_list": [{"title": "Write outline", "status": "todo"}, {"title": "Write draft", "status": "todo"}],
            },
        }),
        task_id="task-001",
    )

    assert event is not None
    assert event.kind is SemanticEventKind.AGENT_TOOL_CALL
    assert event.summary == "Updating task list (2 tasks)"


def test_think_action_is_skipped() -> None:
    event = map_openhands_raw_event(
        _raw("raw-t03", "ActionEvent", {"action": {"kind": "ThinkAction", "thought": "I need to plan..."}}),
        task_id="task-001",
    )

    assert event is None


def test_finish_action_is_skipped() -> None:
    event = map_openhands_raw_event(
        _raw("raw-t04", "ActionEvent", {"action": {"kind": "FinishAction", "message": "Done."}}),
        task_id="task-001",
    )

    assert event is None


def test_unknown_action_event_is_skipped() -> None:
    event = map_openhands_raw_event(
        _raw("raw-t05", "ActionEvent", {"action": {"kind": "UnknownFutureAction"}}),
        task_id="task-001",
    )

    assert event is None
