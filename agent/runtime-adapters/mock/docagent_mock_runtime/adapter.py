from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from docagent_contracts import (
    PromptBundle,
    RuntimeOperationResult,
    RuntimeSessionState,
    SemanticEventKind,
    SemanticTimelineEvent,
    TimelineActor,
    TimelineStatus,
)
from docagent_workspace import checkpoint_draft


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class MockRuntimeAdapter:
    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, object]] = {}

    def create_session(self, session_id: str, prompt_bundle: PromptBundle) -> RuntimeOperationResult:
        self._sessions[session_id] = {
            "task_id": str(prompt_bundle.metadata["task_id"]),
            "workspace_root": prompt_bundle.workspace_root,
            "state": RuntimeSessionState.IDLE,
        }
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.IDLE)

    def send_message(
        self,
        session_id: str,
        message: str,
    ) -> RuntimeOperationResult:
        session = self._session(session_id)
        task_id = str(session["task_id"])
        workspace_root = Path(session["workspace_root"])
        if (workspace_root / "draft" / "draft.md").exists():
            events = self._revise(task_id, session_id, workspace_root, message)
            next_state = RuntimeSessionState.DRAFT_READY
        else:
            events = self._first_draft(task_id, session_id, workspace_root, message)
            next_state = RuntimeSessionState.DRAFT_READY
        self._set_state(session_id, next_state)
        return RuntimeOperationResult(
            session_id=session_id,
            next_state=next_state,
            events=events,
            changed_paths=_event_paths(events),
        )

    def start_loop(self, session_id: str) -> RuntimeOperationResult:
        session = self._session(session_id)
        events = self._build_context_and_outline_events(
            str(session["task_id"]),
            session_id,
            Path(session["workspace_root"]),
        )
        self._set_state(session_id, RuntimeSessionState.AWAIT_OUTLINE_APPROVAL)
        return RuntimeOperationResult(
            session_id=session_id,
            next_state=RuntimeSessionState.AWAIT_OUTLINE_APPROVAL,
            events=events,
            changed_paths=_event_paths(events),
        )

    def approve_outline(self, session_id: str) -> RuntimeOperationResult:
        session = self._session(session_id)
        workspace_root = Path(session["workspace_root"])
        outline_markdown = _read_text(workspace_root / "draft" / "outline.md")
        events = self._approve_outline_and_draft_events(
            str(session["task_id"]),
            session_id,
            workspace_root,
            outline_markdown,
        )
        self._set_state(session_id, RuntimeSessionState.DRAFT_READY)
        return RuntimeOperationResult(
            session_id=session_id,
            next_state=RuntimeSessionState.DRAFT_READY,
            events=events,
            changed_paths=_event_paths(events),
        )

    def revise_selection(
        self,
        session_id: str,
        selection: str,
        instruction: str,
    ) -> RuntimeOperationResult:
        session = self._session(session_id)
        events = self._revise_selection_events(
            str(session["task_id"]),
            session_id,
            Path(session["workspace_root"]),
            selected_text=selection,
            instruction=instruction,
        )
        self._set_state(session_id, RuntimeSessionState.DRAFT_READY)
        return RuntimeOperationResult(
            session_id=session_id,
            next_state=RuntimeSessionState.DRAFT_READY,
            events=events,
            changed_paths=_event_paths(events),
        )

    def run_checklist(self, session_id: str) -> RuntimeOperationResult:
        session = self._session(session_id)
        events = self._run_checklist_events(
            str(session["task_id"]),
            session_id,
            Path(session["workspace_root"]),
        )
        self._set_state(session_id, RuntimeSessionState.DRAFT_READY)
        return RuntimeOperationResult(
            session_id=session_id,
            next_state=RuntimeSessionState.DRAFT_READY,
            events=events,
            changed_paths=_event_paths(events),
        )

    def export_markdown(self, session_id: str) -> RuntimeOperationResult:
        session = self._session(session_id)
        events = self._export_markdown_events(
            str(session["task_id"]),
            session_id,
            Path(session["workspace_root"]),
        )
        self._set_state(session_id, RuntimeSessionState.COMPLETED)
        return RuntimeOperationResult(
            session_id=session_id,
            next_state=RuntimeSessionState.COMPLETED,
            events=events,
            changed_paths=_event_paths(events),
        )

    def cancel(self, session_id: str) -> RuntimeOperationResult:
        self._session(session_id)
        self._set_state(session_id, RuntimeSessionState.CANCELLED)
        return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.CANCELLED)

    def get_state(self, session_id: str) -> RuntimeSessionState:
        return self._session(session_id)["state"]  # type: ignore[return-value]

    def _session(self, session_id: str) -> dict[str, object]:
        if session_id not in self._sessions:
            raise KeyError(f"Unknown runtime session: {session_id}")
        return self._sessions[session_id]

    def _set_state(self, session_id: str, state: RuntimeSessionState) -> None:
        self._session(session_id)["state"] = state

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
        checkpoint = checkpoint_draft(workspace_root, summary=f"Before revision: {message}")
        draft_path = workspace_root / "draft" / "draft.md"
        current = _read_text(draft_path)
        draft_path.write_text(
            current.rstrip() + f"\n\n## Revision note\n\n{message}\n",
            encoding="utf-8",
        )
        return [
            _event(task_id, session_id, "user-2", TimelineActor.USER, SemanticEventKind.USER_MESSAGE, message, []),
            _event(task_id, session_id, "checkpoint-1", TimelineActor.SYSTEM, SemanticEventKind.CREATE_CHECKPOINT, "Create checkpoint", [checkpoint.version_path]),
            _event(task_id, session_id, "draft-2", TimelineActor.AGENT, SemanticEventKind.UPDATE_DRAFT, "Update draft", ["draft/draft.md"]),
        ]

    def _build_context_and_outline_events(
        self,
        task_id: str,
        session_id: str,
        workspace_root: Path,
    ) -> list[SemanticTimelineEvent]:
        (workspace_root / "context").mkdir(parents=True, exist_ok=True)
        (workspace_root / "draft").mkdir(parents=True, exist_ok=True)
        brief = _read_text(workspace_root / "brief.md").strip()
        input_notes = _read_markdown_inputs(workspace_root)
        (workspace_root / "context" / "user_intent.md").write_text(
            f"# User Intent\n\n{brief}\n",
            encoding="utf-8",
        )
        (workspace_root / "context" / "doc_map.md").write_text(
            "# Document Map\n\n- brief.md: user intent\n- inputs/markdown: source materials\n",
            encoding="utf-8",
        )
        (workspace_root / "context" / "style_notes.md").write_text(
            "# Style Notes\n\nUse concise PRD prose, explicit bullets, and decision-ready sections.\n",
            encoding="utf-8",
        )
        (workspace_root / "context" / "structure_notes.md").write_text(
            "# Structure Notes\n\nProblem, Goals, Users, Requirements, Risks, Open Questions.\n",
            encoding="utf-8",
        )
        (workspace_root / "draft" / "outline.md").write_text(
            "# Outline\n\n"
            "1. Problem\n"
            "2. Goals\n"
            "3. Users\n"
            "4. Requirements\n"
            "5. Risks\n"
            "6. Open Questions\n\n"
            f"## Input Signals\n\n{input_notes or '- No additional inputs yet.'}\n",
            encoding="utf-8",
        )
        return [
            _event(task_id, session_id, "skill", TimelineActor.AGENT, SemanticEventKind.READ_SKILL, "Read PRD skill", ["doc-types/prd/SKILL.md"]),
            _event(task_id, session_id, "examples", TimelineActor.AGENT, SemanticEventKind.ANALYZE_EXAMPLES, "Analyze PRD examples", ["doc-types/prd/examples/markdown"]),
            _event(task_id, session_id, "context", TimelineActor.AGENT, SemanticEventKind.BUILD_CONTEXT, "Build context files", ["context/user_intent.md", "context/doc_map.md"]),
            _event(task_id, session_id, "style", TimelineActor.AGENT, SemanticEventKind.EXTRACT_STYLE, "Extract style notes", ["context/style_notes.md"]),
            _event(task_id, session_id, "structure", TimelineActor.AGENT, SemanticEventKind.EXTRACT_STRUCTURE, "Extract structure notes", ["context/structure_notes.md"]),
            _event(task_id, session_id, "outline", TimelineActor.AGENT, SemanticEventKind.PROPOSE_OUTLINE, "Propose outline", ["draft/outline.md"]),
            _event(task_id, session_id, "approval", TimelineActor.SYSTEM, SemanticEventKind.APPROVAL_REQUESTED, "Await outline approval", ["draft/outline.md"]),
        ]

    def _approve_outline_and_draft_events(
        self,
        task_id: str,
        session_id: str,
        workspace_root: Path,
        outline_markdown: str,
    ) -> list[SemanticTimelineEvent]:
        (workspace_root / "draft").mkdir(parents=True, exist_ok=True)
        outline_text = outline_markdown if outline_markdown.endswith("\n") else f"{outline_markdown}\n"
        (workspace_root / "draft" / "outline.md").write_text(outline_text, encoding="utf-8")
        brief = _read_text(workspace_root / "brief.md").strip()
        (workspace_root / "draft" / "draft.md").write_text(
            "# PRD Draft\n\n"
            "## Problem\n\n"
            f"{brief or 'Clarify the product problem.'}\n\n"
            "## Goals\n\n- Define the desired product outcome.\n\n"
            "## Users\n\n- Identify primary users and reviewers.\n\n"
            "## Requirements\n\n- Describe the first usable workflow.\n\n"
            "## Risks\n\n- Validate assumptions before launch.\n",
            encoding="utf-8",
        )
        return [
            _event(task_id, session_id, "outline-approved", TimelineActor.USER, SemanticEventKind.APPROVE_OUTLINE, "Approve outline", ["draft/outline.md"]),
            _event(task_id, session_id, "draft", TimelineActor.AGENT, SemanticEventKind.UPDATE_DRAFT, "Generate draft", ["draft/draft.md"]),
        ]

    def _revise_selection_events(
        self,
        task_id: str,
        session_id: str,
        workspace_root: Path,
        selected_text: str,
        instruction: str,
    ) -> list[SemanticTimelineEvent]:
        draft_path = workspace_root / "draft" / "draft.md"
        if not draft_path.is_file():
            raise FileNotFoundError("Cannot revise missing draft/draft.md")
        current = _read_text(draft_path)
        if selected_text not in current:
            raise ValueError("Selected text not found in draft")
        checkpoint = checkpoint_draft(workspace_root, summary=f"Before selection revision: {instruction}")
        replacement = f"Revised passage: {instruction}"
        draft_path.write_text(current.replace(selected_text, replacement, 1), encoding="utf-8")
        return [
            _event(task_id, session_id, "checkpoint", TimelineActor.SYSTEM, SemanticEventKind.CREATE_CHECKPOINT, "Create checkpoint", [checkpoint.version_path]),
            _event(task_id, session_id, "selection", TimelineActor.AGENT, SemanticEventKind.REVISE_SELECTION, "Revise selected passage", ["draft/draft.md"]),
        ]

    def _run_checklist_events(
        self,
        task_id: str,
        session_id: str,
        workspace_root: Path,
    ) -> list[SemanticTimelineEvent]:
        (workspace_root / "reviews").mkdir(parents=True, exist_ok=True)
        draft = _read_text(workspace_root / "draft" / "draft.md")
        result = "# Checklist Result\n\n- [x] Has draft content\n- [x] Has PRD heading\n"
        if "## Risks" not in draft:
            result += "- [ ] Includes risks section\n"
        else:
            result += "- [x] Includes risks section\n"
        (workspace_root / "reviews" / "checklist_result.md").write_text(result, encoding="utf-8")
        return [_event(task_id, session_id, "checklist", TimelineActor.AGENT, SemanticEventKind.RUN_CHECKLIST, "Run checklist", ["reviews/checklist_result.md"])]

    def _export_markdown_events(
        self,
        task_id: str,
        session_id: str,
        workspace_root: Path,
    ) -> list[SemanticTimelineEvent]:
        (workspace_root / "artifacts").mkdir(parents=True, exist_ok=True)
        artifact_path = workspace_root / "artifacts" / "prd-draft.md"
        artifact_path.write_text(_read_text(workspace_root / "draft" / "draft.md"), encoding="utf-8")
        return [_event(task_id, session_id, "export-md", TimelineActor.SYSTEM, SemanticEventKind.EXPORT_MARKDOWN, "Export Markdown artifact", ["artifacts/prd-draft.md"])]


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _read_markdown_inputs(workspace_root: Path) -> str:
    markdown_dir = workspace_root / "inputs" / "markdown"
    if not markdown_dir.exists():
        return ""
    chunks = []
    for path in sorted(markdown_dir.glob("*.md")):
        chunks.append(f"### {path.name}\n\n{path.read_text(encoding='utf-8').strip()}")
    return "\n\n".join(chunks)


def _event_paths(events: list[SemanticTimelineEvent]) -> list[str]:
    return [path for event in events for path in event.paths]


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
        id=f"{session_id}-{suffix}-{uuid4().hex[:8]}",
        session_id=session_id,
        task_id=task_id,
        actor=actor,
        kind=kind,
        raw_event_id=None,
        summary=summary,
        paths=paths,
        status=TimelineStatus.SUCCEEDED,
        created_at=_utc_now(),
    )
