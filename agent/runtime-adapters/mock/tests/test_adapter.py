from pathlib import Path

from docagent_contracts import PromptBundle, RuntimeSessionState
from docagent_mock_runtime.adapter import MockRuntimeAdapter


def test_first_message_creates_context_outline_draft_and_events(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "brief.md").write_text("Create a pricing PRD\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()
    adapter.create_session("session-001", _prompt_bundle(workspace))
    result = adapter.send_prompt("session-001", "Start drafting", {"action": "send_message"})

    assert (workspace / "context" / "user_intent.md").exists()
    assert (workspace / "context" / "style_notes.md").exists()
    assert (workspace / "context" / "structure_notes.md").exists()
    assert (workspace / "draft" / "outline.md").exists()
    assert "# PRD Draft" in (workspace / "draft" / "draft.md").read_text(encoding="utf-8")
    assert [event.kind.value for event in result.events] == [
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
    adapter.create_session("session-001", _prompt_bundle(workspace))
    result = adapter.send_prompt("session-001", "Tighten the launch section", {"action": "send_message"})

    assert (workspace / "versions" / "v001.md").exists()
    assert "Revision note" in (workspace / "draft" / "draft.md").read_text(encoding="utf-8")
    assert [event.kind.value for event in result.events] == [
        "user_message",
        "create_checkpoint",
        "update_draft",
    ]


def test_later_message_checkpoint_event_uses_actual_version_path(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "draft").mkdir(parents=True)
    (workspace / "draft" / "draft.md").write_text("# Existing\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()
    adapter.create_session("session-001", _prompt_bundle(workspace))
    adapter.send_prompt("session-001", "First revision", {"action": "send_message"})
    result = adapter.send_prompt("session-001", "Second revision", {"action": "send_message"})

    checkpoint_events = [event for event in result.events if event.kind.value == "create_checkpoint"]
    assert checkpoint_events[0].paths == ["versions/v002.md"]


def test_mock_runtime_send_prompt_emits_required_acp_event_families(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "brief.md").write_text("Create a pricing PRD\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()
    adapter.create_session("session-001", _prompt_bundle(workspace))
    result = adapter.send_prompt("session-001", "Build context", {"action": "start_loop"})
    event_types = [update.event_type for update in result.acp_updates]

    assert result.next_state is RuntimeSessionState.AWAIT_OUTLINE_APPROVAL
    assert any("message" in event_type for event_type in event_types)
    assert any("tool" in event_type for event_type in event_types)
    assert any("file" in event_type for event_type in event_types)
    assert any("permission" in event_type or "approval" in event_type for event_type in event_types)
    assert any(event_type.startswith("session/") or "status" in event_type for event_type in event_types)
    assert any("unknown" in event_type for event_type in event_types)
    assert all(update.payload for update in result.acp_updates)


def test_mock_runtime_answers_permission_requests(tmp_path: Path) -> None:
    adapter = MockRuntimeAdapter()
    adapter.create_session("session-001", _prompt_bundle(tmp_path))

    result = adapter.answer_permission("session-001", "permission-1", "deny")

    assert result.next_state is RuntimeSessionState.IDLE
    assert [update.event_type for update in result.acp_updates] == ["permission/resolved"]
    assert result.acp_updates[0].payload == {"request_id": "permission-1", "decision": "deny"}


def test_mock_runtime_generates_skill_creator_artifacts(tmp_path: Path) -> None:
    adapter = MockRuntimeAdapter()
    adapter.create_session("creator-001", _skill_creator_prompt_bundle(tmp_path))

    result = adapter.send_prompt("creator-001", "Generate memo pack", {"action": "skill_creator_generate"})

    assert "SKILL.md" in result.changed_paths
    assert (tmp_path / "SKILL.md").is_file()
    assert (tmp_path / "checklists" / "quality.yaml").is_file()
    assert any(update.event_type == "file/write" for update in result.acp_updates)


def test_mock_runtime_skill_creator_revision_reads_existing_skill(tmp_path: Path) -> None:
    (tmp_path / "SKILL.md").write_text(
        "---\nname: memo\ndescription: Use for memos.\n---\n\n# Memo\n\nPreserve this line.\n",
        encoding="utf-8",
    )
    adapter = MockRuntimeAdapter()
    adapter.create_session("creator-001", _skill_creator_prompt_bundle(tmp_path))

    result = adapter.send_prompt("creator-001", "Revise without removing manual edits", {"action": "skill_creator_message"})
    event_types = [update.event_type for update in result.acp_updates]

    assert "Preserve this line." in (tmp_path / "SKILL.md").read_text(encoding="utf-8")
    assert "file/read" in event_types
    assert event_types.index("file/read") < event_types.index("file/write")


def _prompt_bundle(workspace: Path) -> PromptBundle:
    return PromptBundle(
        system_prompt="system",
        task_instruction="task",
        workspace_root=workspace,
        doc_type_id="prd",
        metadata={"task_id": "task-001"},
    )


def _skill_creator_prompt_bundle(workspace: Path) -> PromptBundle:
    return PromptBundle(
        system_prompt="system",
        task_instruction="task",
        workspace_root=workspace,
        doc_type_id="",
        pack_id="memo",
        metadata={"session_scope": "pack-management", "pack_id": "memo"},
    )
