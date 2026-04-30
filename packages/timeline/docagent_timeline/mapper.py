from __future__ import annotations

from docagent_contracts import SemanticEventKind, SemanticTimelineEvent, TimelineActor, TimelineStatus


def _kind_and_summary(action: str, path: str | None, command: str | None) -> tuple[SemanticEventKind, str]:
    normalized_path = (path or "").replace("\\", "/")
    normalized_command = command or ""

    if normalized_path.endswith("/SKILL.md") or normalized_path.endswith("SKILL.md"):
        return SemanticEventKind.READ_SKILL, "Read document type skill"
    if "/examples/" in normalized_path and action == "read_file":
        return SemanticEventKind.ANALYZE_EXAMPLES, "Analyze best-practice examples"
    if normalized_path.endswith("context/style_notes.md"):
        return SemanticEventKind.EXTRACT_STYLE, "Extract style notes"
    if normalized_path.endswith("context/structure_notes.md"):
        return SemanticEventKind.EXTRACT_STRUCTURE, "Extract structure notes"
    if normalized_path.endswith("draft/outline.md"):
        return SemanticEventKind.GENERATE_OUTLINE, "Generate outline"
    if normalized_path.endswith("draft/draft.md"):
        return SemanticEventKind.UPDATE_DRAFT, "Update draft"
    if "checkpoint.py" in normalized_command:
        return SemanticEventKind.CREATE_CHECKPOINT, "Create checkpoint"
    if normalized_path.endswith("reviews/checklist_result.md"):
        return SemanticEventKind.RUN_CHECKLIST, "Run checklist"
    if "export_docx.py" in normalized_command:
        return SemanticEventKind.EXPORT_DOCX, "Export DOCX"

    return SemanticEventKind.AGENT_MESSAGE, "Agent event"


def map_raw_event(
    raw_event_id: str,
    task_id: str,
    session_id: str,
    actor: str,
    action: str,
    path: str | None,
    command: str | None,
    status: str,
    created_at: str,
) -> SemanticTimelineEvent:
    kind, summary = _kind_and_summary(action, path, command)
    paths = [path] if path else []
    return SemanticTimelineEvent(
        id=f"sem-{raw_event_id}",
        session_id=session_id,
        task_id=task_id,
        actor=TimelineActor(actor),
        kind=kind,
        raw_event_id=raw_event_id,
        summary=summary,
        paths=paths,
        status=TimelineStatus(status),
        created_at=created_at,
    )
