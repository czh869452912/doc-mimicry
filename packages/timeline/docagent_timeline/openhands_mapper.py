from __future__ import annotations

from docagent_contracts import (
    RawRuntimeEvent,
    SemanticEventKind,
    SemanticTimelineEvent,
    TimelineActor,
    TimelineStatus,
)

_SUMMARY: dict[SemanticEventKind, str] = {
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
    SemanticEventKind.ERROR: "Runtime error",
}


def map_openhands_raw_event(raw_event: RawRuntimeEvent, task_id: str) -> SemanticTimelineEvent | None:
    kind, summary = _classify(raw_event)
    if kind is None:
        return None
    path = _path(raw_event)
    return SemanticTimelineEvent(
        id=f"sem-{raw_event.id}",
        session_id=raw_event.session_id,
        task_id=task_id,
        actor=TimelineActor.AGENT,
        kind=kind,
        raw_event_id=raw_event.id,
        summary=summary,
        paths=[path] if path else [],
        status=TimelineStatus.SUCCEEDED,
        created_at=raw_event.created_at,
    )


def _classify(raw_event: RawRuntimeEvent) -> tuple[SemanticEventKind | None, str]:
    if raw_event.kind == "cancelled":
        return SemanticEventKind.ERROR, _SUMMARY[SemanticEventKind.ERROR]

    # Conversation-level failures surfaced by the OpenHands runtime
    if raw_event.kind == "ConversationErrorEvent":
        code = raw_event.payload.get("code") or ""
        detail = (raw_event.payload.get("detail") or "Conversation error")[:200]
        summary = f"Agent error ({code}): {detail}" if code else detail
        return SemanticEventKind.ERROR, summary

    # Extract LLM text responses from agent MessageEvents
    if raw_event.kind == "MessageEvent" and raw_event.payload.get("source") == "agent":
        llm_message = raw_event.payload.get("llm_message") or {}
        for part in llm_message.get("content") or []:
            if isinstance(part, dict) and part.get("type") == "text":
                text = (part.get("text") or "").strip()
                if text:
                    return SemanticEventKind.AGENT_MESSAGE, text
        return None, ""

    # Map visible chat-mode tool calls; file-writing actions fall through to path matching
    if raw_event.kind == "ActionEvent":
        action = raw_event.payload.get("action") or {}
        action_kind = action.get("kind", "")
        if action_kind in ("ThinkAction", "FinishAction"):
            return None, ""
        if action_kind == "TaskTrackerAction":
            command = action.get("command", "")
            if command == "plan":
                n = len(action.get("task_list") or [])
                return SemanticEventKind.AGENT_TOOL_CALL, f"Updating task list ({n} tasks)"
            return SemanticEventKind.AGENT_TOOL_CALL, "Checking task list"
        # FileEditorAction, TerminalAction, etc. fall through to path-based matching

    # Skip ObservationEvents — the preceding ActionEvent already captures the intent
    # and has the same path, so this avoids duplicate semantic events for file writes
    if raw_event.kind == "ObservationEvent":
        return None, ""

    path = _path(raw_event)
    if path is None:
        return None, ""

    if path.endswith("doc-types/prd/SKILL.md") or path.endswith("SKILL.md"):
        return SemanticEventKind.READ_SKILL, _SUMMARY[SemanticEventKind.READ_SKILL]
    if "/examples/" in path:
        return SemanticEventKind.ANALYZE_EXAMPLES, _SUMMARY[SemanticEventKind.ANALYZE_EXAMPLES]
    if path.endswith("context/user_intent.md") or path.endswith("context/doc_map.md"):
        return SemanticEventKind.BUILD_CONTEXT, _SUMMARY[SemanticEventKind.BUILD_CONTEXT]
    if path.endswith("context/style_notes.md"):
        return SemanticEventKind.EXTRACT_STYLE, _SUMMARY[SemanticEventKind.EXTRACT_STYLE]
    if path.endswith("context/structure_notes.md"):
        return SemanticEventKind.EXTRACT_STRUCTURE, _SUMMARY[SemanticEventKind.EXTRACT_STRUCTURE]
    if path.endswith("draft/outline.md"):
        return SemanticEventKind.PROPOSE_OUTLINE, _SUMMARY[SemanticEventKind.PROPOSE_OUTLINE]
    if path.endswith("draft/draft.md"):
        return SemanticEventKind.UPDATE_DRAFT, _SUMMARY[SemanticEventKind.UPDATE_DRAFT]
    if path.startswith("versions/"):
        return SemanticEventKind.CREATE_CHECKPOINT, _SUMMARY[SemanticEventKind.CREATE_CHECKPOINT]
    if path.endswith("reviews/checklist_result.md"):
        return SemanticEventKind.RUN_CHECKLIST, _SUMMARY[SemanticEventKind.RUN_CHECKLIST]
    if path.endswith("artifacts/prd-draft.md"):
        return SemanticEventKind.EXPORT_MARKDOWN, _SUMMARY[SemanticEventKind.EXPORT_MARKDOWN]
    return None, ""


def _path(raw_event: RawRuntimeEvent) -> str | None:
    value = raw_event.payload.get("path") or raw_event.payload.get("file_path")
    if value is None:
        return None
    path = str(value).replace("\\", "/")
    workspace_root = raw_event.payload.get("workspace_root")
    if isinstance(workspace_root, str) and workspace_root:
        root = workspace_root.replace("\\", "/").rstrip("/")
        if path == root:
            return ""
        prefix = f"{root}/"
        if path.startswith(prefix):
            return path[len(prefix):]
    marker = "/workspaces/"
    if marker in path:
        parts = path.split(marker, 1)[1].split("/", 1)
        if len(parts) == 2:
            return parts[1]
    return path
