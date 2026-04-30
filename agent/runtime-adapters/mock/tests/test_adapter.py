from pathlib import Path

from docagent_mock_runtime.adapter import MockRuntimeAdapter


def test_first_message_creates_context_outline_draft_and_events(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "brief.md").write_text("Create a pricing PRD\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()
    events = adapter.send_message(
        task_id="task-001",
        session_id="session-001",
        workspace_root=workspace,
        message="Start drafting",
    )

    assert (workspace / "context" / "user_intent.md").exists()
    assert (workspace / "context" / "style_notes.md").exists()
    assert (workspace / "context" / "structure_notes.md").exists()
    assert (workspace / "draft" / "outline.md").exists()
    assert "# PRD Draft" in (workspace / "draft" / "draft.md").read_text(encoding="utf-8")
    assert [event.kind.value for event in events] == [
        "user_message",
        "read_skill",
        "extract_style",
        "extract_structure",
        "generate_outline",
        "update_draft",
    ]


def test_later_message_checkpoints_and_updates_draft(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "draft").mkdir(parents=True)
    (workspace / "draft" / "draft.md").write_text("# Existing\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()
    events = adapter.send_message(
        task_id="task-001",
        session_id="session-001",
        workspace_root=workspace,
        message="Tighten the launch section",
    )

    assert (workspace / "versions" / "v001.md").exists()
    assert "Revision note" in (workspace / "draft" / "draft.md").read_text(encoding="utf-8")
    assert [event.kind.value for event in events] == [
        "user_message",
        "create_checkpoint",
        "update_draft",
    ]
