from pathlib import Path

import pytest

from docagent_mock_runtime.adapter import MockRuntimeAdapter


def test_build_context_and_propose_outline(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "inputs" / "markdown").mkdir(parents=True)
    (workspace / "brief.md").write_text("Build a PRD for onboarding analytics\n", encoding="utf-8")
    (workspace / "inputs" / "markdown" / "notes.md").write_text("Users need funnel visibility.\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()
    events = adapter.build_context_and_outline("task-001", "session-001", workspace)

    assert (workspace / "context" / "user_intent.md").exists()
    assert (workspace / "context" / "doc_map.md").exists()
    assert (workspace / "draft" / "outline.md").exists()
    assert [event.kind.value for event in events] == [
        "read_skill",
        "analyze_examples",
        "build_context",
        "extract_style",
        "extract_structure",
        "propose_outline",
        "approval_requested",
    ]


def test_repeated_outline_builds_emit_unique_event_ids(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "brief.md").write_text("Build a PRD for onboarding analytics\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()
    first_events = adapter.build_context_and_outline("task-001", "session-001", workspace)
    second_events = adapter.build_context_and_outline("task-001", "session-001", workspace)

    event_ids = [event.id for event in first_events + second_events]
    assert len(event_ids) == len(set(event_ids))


def test_approve_outline_generates_draft(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "draft").mkdir(parents=True)
    (workspace / "brief.md").write_text("Build a PRD for onboarding analytics\n", encoding="utf-8")
    (workspace / "draft" / "outline.md").write_text("# Outline\n\n1. Problem\n2. Goals\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()
    events = adapter.approve_outline_and_draft("task-001", "session-001", workspace, "# Outline\n\n1. Problem\n2. Goals\n")

    assert "# PRD Draft" in (workspace / "draft" / "draft.md").read_text(encoding="utf-8")
    assert [event.kind.value for event in events] == ["approve_outline", "update_draft"]


def test_revise_selection_checkpoints_and_replaces_text(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "draft").mkdir(parents=True)
    (workspace / "draft" / "draft.md").write_text("# PRD Draft\n\nOld passage\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()
    events = adapter.revise_selection(
        "task-001",
        "session-001",
        workspace,
        selected_text="Old passage",
        instruction="Make it sharper",
    )

    draft = (workspace / "draft" / "draft.md").read_text(encoding="utf-8")
    assert "Old passage" not in draft
    assert "Make it sharper" in draft
    assert (workspace / "versions" / "v001.md").exists()
    assert [event.kind.value for event in events] == ["create_checkpoint", "revise_selection"]


def test_revise_selection_raises_when_selected_text_is_missing(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "draft").mkdir(parents=True)
    (workspace / "draft" / "draft.md").write_text("# PRD Draft\n\nOld passage\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()

    with pytest.raises(ValueError, match="Selected text not found in draft"):
        adapter.revise_selection(
            "task-001",
            "session-001",
            workspace,
            selected_text="Missing passage",
            instruction="Make it sharper",
        )


def test_run_checklist_and_export_markdown(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "draft").mkdir(parents=True)
    (workspace / "draft" / "draft.md").write_text("# PRD Draft\n\n## Goals\n\n- Improve activation\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()
    checklist_events = adapter.run_checklist("task-001", "session-001", workspace)
    export_events = adapter.export_markdown("task-001", "session-001", workspace)

    assert (workspace / "reviews" / "checklist_result.md").exists()
    assert (workspace / "artifacts" / "prd-draft.md").exists()
    assert [event.kind.value for event in checklist_events] == ["run_checklist"]
    assert [event.kind.value for event in export_events] == ["export_markdown"]
