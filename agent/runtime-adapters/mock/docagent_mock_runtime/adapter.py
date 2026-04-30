from __future__ import annotations

from pathlib import Path

from docagent_contracts import (
    SemanticEventKind,
    SemanticTimelineEvent,
    TimelineActor,
    TimelineStatus,
)
from docagent_workspace import checkpoint_draft


class MockRuntimeAdapter:
    def send_message(
        self,
        task_id: str,
        session_id: str,
        workspace_root: Path,
        message: str,
    ) -> list[SemanticTimelineEvent]:
        if (workspace_root / "draft" / "draft.md").exists():
            return self._revise(task_id, session_id, workspace_root, message)
        return self._first_draft(task_id, session_id, workspace_root, message)

    def _first_draft(
        self,
        task_id: str,
        session_id: str,
        workspace_root: Path,
        message: str,
    ) -> list[SemanticTimelineEvent]:
        (workspace_root / "context").mkdir(parents=True, exist_ok=True)
        (workspace_root / "draft").mkdir(parents=True, exist_ok=True)
        brief = _read_text(workspace_root / "brief.md")
        (workspace_root / "context" / "user_intent.md").write_text(
            f"# User Intent\n\n{brief}",
            encoding="utf-8",
        )
        (workspace_root / "context" / "style_notes.md").write_text(
            "# Style Notes\n\nMirror structure and narration patterns from converted Markdown examples.\n",
            encoding="utf-8",
        )
        (workspace_root / "context" / "structure_notes.md").write_text(
            "# Structure Notes\n\nUse a concise PRD structure with goals, users, requirements, and risks.\n",
            encoding="utf-8",
        )
        (workspace_root / "draft" / "outline.md").write_text(
            "# Outline\n\n1. Background\n2. Goals\n3. Requirements\n4. Risks\n",
            encoding="utf-8",
        )
        (workspace_root / "draft" / "draft.md").write_text(
            "# PRD Draft\n\n"
            "## Background\n\n"
            f"{brief.strip()}\n\n"
            "## Goals\n\n- Clarify the product outcome.\n\n"
            "## Requirements\n\n- Capture the first usable behavior.\n\n"
            "## Risks\n\n- Validate assumptions with users.\n",
            encoding="utf-8",
        )
        return [
            _event(task_id, session_id, "user-1", TimelineActor.USER, SemanticEventKind.USER_MESSAGE, message, []),
            _event(task_id, session_id, "skill-1", TimelineActor.AGENT, SemanticEventKind.READ_SKILL, "Read document type skill", ["doc-types/prd/SKILL.md"]),
            _event(task_id, session_id, "style-1", TimelineActor.AGENT, SemanticEventKind.EXTRACT_STYLE, "Extract style notes", ["context/style_notes.md"]),
            _event(task_id, session_id, "structure-1", TimelineActor.AGENT, SemanticEventKind.EXTRACT_STRUCTURE, "Extract structure notes", ["context/structure_notes.md"]),
            _event(task_id, session_id, "outline-1", TimelineActor.AGENT, SemanticEventKind.GENERATE_OUTLINE, "Generate outline", ["draft/outline.md"]),
            _event(task_id, session_id, "draft-1", TimelineActor.AGENT, SemanticEventKind.UPDATE_DRAFT, "Update draft", ["draft/draft.md"]),
        ]

    def _revise(
        self,
        task_id: str,
        session_id: str,
        workspace_root: Path,
        message: str,
    ) -> list[SemanticTimelineEvent]:
        checkpoint_draft(workspace_root, summary=f"Before revision: {message}")
        draft_path = workspace_root / "draft" / "draft.md"
        current = _read_text(draft_path)
        draft_path.write_text(
            current.rstrip() + f"\n\n## Revision note\n\n{message}\n",
            encoding="utf-8",
        )
        return [
            _event(task_id, session_id, "user-2", TimelineActor.USER, SemanticEventKind.USER_MESSAGE, message, []),
            _event(task_id, session_id, "checkpoint-1", TimelineActor.SYSTEM, SemanticEventKind.CREATE_CHECKPOINT, "Create checkpoint", ["versions/v001.md"]),
            _event(task_id, session_id, "draft-2", TimelineActor.AGENT, SemanticEventKind.UPDATE_DRAFT, "Update draft", ["draft/draft.md"]),
        ]


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _event(
    task_id: str,
    session_id: str,
    suffix: str,
    actor: TimelineActor,
    kind: SemanticEventKind,
    summary: str,
    paths: list[str],
) -> SemanticTimelineEvent:
    return SemanticTimelineEvent(
        id=f"{session_id}-{suffix}",
        session_id=session_id,
        task_id=task_id,
        actor=actor,
        kind=kind,
        raw_event_id=None,
        summary=summary,
        paths=paths,
        status=TimelineStatus.SUCCEEDED,
        created_at="2026-04-30T00:00:00Z",
    )
