from docagent_contracts import RawRuntimeEvent, RuntimeKind, SemanticEventKind
from docagent_timeline import map_openhands_raw_event


def test_maps_openhands_outline_path_to_propose_outline() -> None:
    event = map_openhands_raw_event(
        RawRuntimeEvent(
            id="raw-001",
            session_id="session-001",
            runtime=RuntimeKind.OPENHANDS,
            runtime_session_id="openhands-001",
            kind="file_written",
            payload={"path": "draft/outline.md"},
            created_at="2026-05-06T00:00:00Z",
        ),
        task_id="task-001",
    )

    assert event.kind is SemanticEventKind.PROPOSE_OUTLINE
    assert event.raw_event_id == "raw-001"


def test_maps_openhands_artifact_path_to_export_markdown() -> None:
    event = map_openhands_raw_event(
        RawRuntimeEvent(
            id="raw-002",
            session_id="session-001",
            runtime=RuntimeKind.OPENHANDS,
            runtime_session_id="openhands-001",
            kind="file_written",
            payload={"path": "artifacts/prd-draft.md"},
            created_at="2026-05-06T00:00:00Z",
        ),
        task_id="task-001",
    )

    assert event.kind is SemanticEventKind.EXPORT_MARKDOWN
