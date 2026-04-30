from docagent_contracts import SemanticEventKind
from docagent_timeline import map_raw_event


def test_maps_skill_read():
    event = map_raw_event(
        raw_event_id="raw-001",
        task_id="task-001",
        session_id="session-001",
        actor="tool",
        action="read_file",
        path="/doc-types/prd/SKILL.md",
        command=None,
        status="succeeded",
        created_at="2026-04-30T00:00:00Z",
    )

    assert event.kind is SemanticEventKind.READ_SKILL
    assert event.summary == "Read document type skill"


def test_maps_style_notes_write():
    event = map_raw_event(
        raw_event_id="raw-002",
        task_id="task-001",
        session_id="session-001",
        actor="tool",
        action="write_file",
        path="context/style_notes.md",
        command=None,
        status="succeeded",
        created_at="2026-04-30T00:00:00Z",
    )

    assert event.kind is SemanticEventKind.EXTRACT_STYLE


def test_maps_checkpoint_command():
    event = map_raw_event(
        raw_event_id="raw-003",
        task_id="task-001",
        session_id="session-001",
        actor="tool",
        action="execute_bash",
        path=None,
        command="python tools/workspace/checkpoint.py --workspace x",
        status="succeeded",
        created_at="2026-04-30T00:00:00Z",
    )

    assert event.kind is SemanticEventKind.CREATE_CHECKPOINT
