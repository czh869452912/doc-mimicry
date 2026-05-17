from pathlib import Path

import pytest

from docagent_contracts import PromptBundle
from docagent_mock_runtime.adapter import MockRuntimeAdapter


def test_build_context_and_propose_outline(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "inputs" / "markdown").mkdir(parents=True)
    (workspace / "brief.md").write_text("Build a PRD for onboarding analytics\n", encoding="utf-8")
    (workspace / "inputs" / "markdown" / "notes.md").write_text("Users need funnel visibility.\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()
    adapter.create_session("session-001", _prompt_bundle(workspace))
    result = adapter.send_prompt("session-001", "Build context", {"action": "start_loop"})

    assert (workspace / "context" / "user_intent.md").exists()
    assert (workspace / "context" / "doc_map.md").exists()
    assert (workspace / "draft" / "outline.md").exists()
    assert [event.kind.value for event in result.events] == [
        "read_skill",
        "analyze_examples",
        "build_context",
        "extract_style",
        "extract_structure",
        "propose_outline",
        "approval_requested",
    ]


def test_non_prd_outline_uses_doc_type_paths_and_generic_language(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "brief.md").write_text("Write a board memo about renewals\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()
    adapter.create_session("session-001", _prompt_bundle(workspace, doc_type_id="memo"))
    result = adapter.send_prompt("session-001", "Build context", {"action": "start_loop"})

    assert (workspace / "context" / "style_notes.md").read_text(encoding="utf-8").startswith("# Style Notes")
    assert "PRD" not in (workspace / "context" / "style_notes.md").read_text(encoding="utf-8")
    assert result.events[0].paths == ["doc-types/memo/SKILL.md"]
    assert result.events[1].paths == ["doc-types/memo/examples/markdown"]
    assert result.events[0].summary == "Read memo skill"
    assert result.events[1].summary == "Analyze memo examples"


def test_repeated_outline_builds_emit_unique_event_ids(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "brief.md").write_text("Build a PRD for onboarding analytics\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()
    adapter.create_session("session-001", _prompt_bundle(workspace))
    first_events = adapter.send_prompt("session-001", "Build context", {"action": "start_loop"}).events
    second_events = adapter.send_prompt("session-001", "Build context", {"action": "start_loop"}).events

    event_ids = [event.id for event in first_events + second_events]
    assert len(event_ids) == len(set(event_ids))


def test_approve_outline_generates_draft(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "draft").mkdir(parents=True)
    (workspace / "brief.md").write_text("Build a PRD for onboarding analytics\n", encoding="utf-8")
    (workspace / "draft" / "outline.md").write_text("# Outline\n\n1. Problem\n2. Goals\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()
    adapter.create_session("session-001", _prompt_bundle(workspace))
    result = adapter.send_prompt("session-001", "Approve outline", {"action": "approve_outline"})

    assert "# PRD Draft" in (workspace / "draft" / "draft.md").read_text(encoding="utf-8")
    assert [event.kind.value for event in result.events] == ["approve_outline", "update_draft"]


def test_non_prd_draft_and_export_use_doc_type_heading_and_path(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "draft").mkdir(parents=True)
    (workspace / "brief.md").write_text("Write a board memo about renewals\n", encoding="utf-8")
    (workspace / "draft" / "outline.md").write_text("# Outline\n\n1. Context\n2. Recommendation\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()
    adapter.create_session("session-001", _prompt_bundle(workspace, doc_type_id="memo"))
    adapter.send_prompt("session-001", "Approve outline", {"action": "approve_outline"})
    export_events = adapter.send_prompt("session-001", "Export Markdown", {"action": "export_markdown"}).events

    draft = (workspace / "draft" / "draft.md").read_text(encoding="utf-8")
    assert "# Memo Draft" in draft
    assert "# PRD Draft" not in draft
    assert (workspace / "artifacts" / "memo-draft.md").exists()
    assert export_events[0].paths == ["artifacts/memo-draft.md"]


def test_revise_selection_checkpoints_and_replaces_text(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "draft").mkdir(parents=True)
    (workspace / "draft" / "draft.md").write_text("# PRD Draft\n\nOld passage\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()
    adapter.create_session("session-001", _prompt_bundle(workspace))
    result = adapter.send_prompt(
        "session-001",
        "Make it sharper",
        {"action": "revise_selection", "selection": "Old passage"},
    )

    draft = (workspace / "draft" / "draft.md").read_text(encoding="utf-8")
    assert "Old passage" not in draft
    assert "Make it sharper" in draft
    assert (workspace / "versions" / "v001.md").exists()
    assert [event.kind.value for event in result.events] == ["create_checkpoint", "revise_selection"]


def test_revise_selection_raises_when_selected_text_is_missing(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "draft").mkdir(parents=True)
    (workspace / "draft" / "draft.md").write_text("# PRD Draft\n\nOld passage\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()
    adapter.create_session("session-001", _prompt_bundle(workspace))

    with pytest.raises(ValueError, match="Selected text not found in draft"):
        adapter.send_prompt(
            "session-001",
            "Make it sharper",
            {"action": "revise_selection", "selection": "Missing passage"},
        )

    assert not (workspace / "versions").exists() or not any((workspace / "versions").iterdir())


def test_run_checklist_and_export_markdown(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "draft").mkdir(parents=True)
    (workspace / "draft" / "draft.md").write_text("# PRD Draft\n\n## Goals\n\n- Improve activation\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()
    adapter.create_session("session-001", _prompt_bundle(workspace))
    checklist_events = adapter.send_prompt("session-001", "Run checklist", {"action": "run_checklist"}).events
    export_events = adapter.send_prompt("session-001", "Export Markdown", {"action": "export_markdown"}).events

    assert (workspace / "reviews" / "checklist_result.md").exists()
    assert (workspace / "artifacts" / "prd-draft.md").exists()
    assert [event.kind.value for event in checklist_events] == ["run_checklist"]
    assert [event.kind.value for event in export_events] == ["export_markdown"]


def _prompt_bundle(workspace: Path, doc_type_id: str = "prd") -> PromptBundle:
    return PromptBundle(
        system_prompt="system",
        task_instruction="task",
        workspace_root=workspace,
        doc_type_id=doc_type_id,
        metadata={"task_id": "task-001"},
    )
