from __future__ import annotations

from docagent_contracts import (
    RawRuntimeEvent,
    SemanticEventKind,
    SemanticTimelineEvent,
    TimelineActor,
    TimelineStatus,
)


def map_openhands_raw_event(raw_event: RawRuntimeEvent, task_id: str) -> SemanticTimelineEvent:
    path = _path(raw_event)
    kind = _kind(raw_event.kind, path)
    return SemanticTimelineEvent(
        id=f"sem-{raw_event.id}",
        session_id=raw_event.session_id,
        task_id=task_id,
        actor=TimelineActor.AGENT,
        kind=kind,
        raw_event_id=raw_event.id,
        summary=_summary(kind),
        paths=[path] if path else [],
        status=TimelineStatus.SUCCEEDED,
        created_at=raw_event.created_at,
    )


def _path(raw_event: RawRuntimeEvent) -> str | None:
    value = raw_event.payload.get("path") or raw_event.payload.get("file_path")
    if value is None:
        return None
    return str(value).replace("\\", "/")


def _kind(raw_kind: str, path: str | None) -> SemanticEventKind:
    if raw_kind == "cancelled":
        return SemanticEventKind.ERROR
    if path is None:
        return SemanticEventKind.AGENT_MESSAGE
    if path.endswith("doc-types/prd/SKILL.md") or path.endswith("SKILL.md"):
        return SemanticEventKind.READ_SKILL
    if "/examples/" in path:
        return SemanticEventKind.ANALYZE_EXAMPLES
    if path.endswith("context/user_intent.md") or path.endswith("context/doc_map.md"):
        return SemanticEventKind.BUILD_CONTEXT
    if path.endswith("context/style_notes.md"):
        return SemanticEventKind.EXTRACT_STYLE
    if path.endswith("context/structure_notes.md"):
        return SemanticEventKind.EXTRACT_STRUCTURE
    if path.endswith("draft/outline.md"):
        return SemanticEventKind.PROPOSE_OUTLINE
    if path.endswith("draft/draft.md"):
        return SemanticEventKind.UPDATE_DRAFT
    if path.startswith("versions/"):
        return SemanticEventKind.CREATE_CHECKPOINT
    if path.endswith("reviews/checklist_result.md"):
        return SemanticEventKind.RUN_CHECKLIST
    if path.endswith("artifacts/prd-draft.md"):
        return SemanticEventKind.EXPORT_MARKDOWN
    return SemanticEventKind.AGENT_MESSAGE


def _summary(kind: SemanticEventKind) -> str:
    return {
        SemanticEventKind.READ_SKILL: "Read document type skill",
        SemanticEventKind.ANALYZE_EXAMPLES: "Analyze examples",
        SemanticEventKind.BUILD_CONTEXT: "Build context",
        SemanticEventKind.EXTRACT_STYLE: "Extract style notes",
        SemanticEventKind.EXTRACT_STRUCTURE: "Extract structure notes",
        SemanticEventKind.PROPOSE_OUTLINE: "Propose outline",
        SemanticEventKind.UPDATE_DRAFT: "Update draft",
        SemanticEventKind.CREATE_CHECKPOINT: "Create checkpoint",
        SemanticEventKind.RUN_CHECKLIST: "Run checklist",
        SemanticEventKind.EXPORT_MARKDOWN: "Export Markdown artifact",
        SemanticEventKind.ERROR: "Runtime event",
    }.get(kind, "Agent event")
