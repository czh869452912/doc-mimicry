from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from docagent_api.doctypes import get_doc_type, list_doc_types
from docagent_api.drafts import read_draft, write_draft
from docagent_api.imports import import_text_input
from docagent_api.state import DocAgentState
from docagent_api.workspace_files import list_workspace_files, read_workspace_text_file
from docagent_contracts import SemanticEventKind, SemanticTimelineEvent, TimelineActor, TimelineStatus
from docagent_mock_runtime.adapter import MockRuntimeAdapter
from docagent_workspace import create_workspace


class CreateTaskRequest(BaseModel):
    doc_type_id: str
    brief: str


class SendMessageRequest(BaseModel):
    message: str


class ImportTextRequest(BaseModel):
    name: str
    content: str


class ApproveOutlineRequest(BaseModel):
    outline_markdown: str


class ReviseSelectionRequest(BaseModel):
    selected_text: str
    instruction: str


class UpdateDraftRequest(BaseModel):
    markdown: str


def create_app(state_root: Path | None = None, repo_root: Path | None = None) -> FastAPI:
    app = FastAPI(title="DocAgent Workbench API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    root = repo_root or Path.cwd()
    state = DocAgentState(state_root or root / ".local" / "docagent")
    adapter = MockRuntimeAdapter()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/doc-types")
    def doc_types() -> list[dict[str, Any]]:
        return list_doc_types(root / "doc-types")

    @app.get("/doc-types/{doc_type_id}")
    def doc_type_detail(doc_type_id: str) -> dict[str, Any]:
        detail = get_doc_type(root / "doc-types", doc_type_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Document type not found")
        return detail

    @app.get("/tasks")
    def list_tasks() -> list[dict[str, Any]]:
        return state.list_tasks()

    @app.post("/tasks")
    def create_task(request: CreateTaskRequest) -> dict[str, Any]:
        if get_doc_type(root / "doc-types", request.doc_type_id) is None:
            raise HTTPException(status_code=404, detail="Document type not found")
        task_id = f"task-{uuid4().hex[:8]}"
        workspace_root = state.workspace_root(task_id)
        create_workspace(workspace_root, request.brief)
        record = {
            "id": task_id,
            "doc_type_id": request.doc_type_id,
            "brief": request.brief,
            "workspace_root": str(workspace_root),
            "created_at": "2026-04-30T00:00:00Z",
            "updated_at": "2026-04-30T00:00:00Z",
        }
        state.save_task(record)
        return record

    @app.get("/tasks/{task_id}")
    def get_task(task_id: str) -> dict[str, Any]:
        return _require_task(state, task_id)

    @app.get("/tasks/{task_id}/workspace")
    def get_workspace(task_id: str) -> dict[str, Any]:
        task = _require_task(state, task_id)
        workspace_root = Path(task["workspace_root"])
        return {"task_id": task_id, "root": str(workspace_root), "files": list_workspace_files(workspace_root)}

    @app.get("/tasks/{task_id}/workspace/files")
    def get_workspace_file(task_id: str, file_path: str = Query(alias="path")) -> dict[str, str]:
        task = _require_task(state, task_id)
        try:
            content = read_workspace_text_file(Path(task["workspace_root"]), file_path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Workspace file not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"path": file_path, "content": content}

    @app.get("/tasks/{task_id}/draft")
    def get_draft(task_id: str) -> dict[str, str]:
        task = _require_task(state, task_id)
        return {"task_id": task_id, "markdown": read_draft(Path(task["workspace_root"]))}

    @app.put("/tasks/{task_id}/draft")
    def update_draft(task_id: str, request: UpdateDraftRequest) -> dict[str, str]:
        task = _require_task(state, task_id)
        write_draft(Path(task["workspace_root"]), request.markdown)
        return {"task_id": task_id, "markdown": read_draft(Path(task["workspace_root"]))}

    @app.post("/tasks/{task_id}/sessions")
    def create_session(task_id: str) -> dict[str, Any]:
        _require_task(state, task_id)
        session_id = f"session-{uuid4().hex[:8]}"
        record = {
            "id": session_id,
            "task_id": task_id,
            "status": "idle",
            "created_at": "2026-04-30T00:00:00Z",
            "updated_at": "2026-04-30T00:00:00Z",
        }
        state.save_session(record)
        return record

    @app.get("/tasks/{task_id}/sessions")
    def list_task_sessions(task_id: str) -> list[dict[str, Any]]:
        _require_task(state, task_id)
        return [session for session in state.list_sessions() if session["task_id"] == task_id]

    @app.post("/tasks/{task_id}/inputs/text")
    def add_text_input(task_id: str, request: ImportTextRequest) -> dict[str, Any]:
        task = _require_task(state, task_id)
        result = import_text_input(
            Path(task["workspace_root"]),
            request.name,
            request.content,
            "2026-04-30T00:00:00Z",
        )
        sessions = [session for session in state.list_sessions() if session["task_id"] == task_id]
        if sessions:
            event = _manual_event(
                task_id,
                sessions[0]["id"],
                f"convert-input-{result['id']}",
                TimelineActor.SYSTEM,
                SemanticEventKind.CONVERT_INPUT,
                "Convert input to Markdown",
                [result["markdown_path"], result["conversion_report_path"]],
            )
            state.append_timeline_event(sessions[0]["id"], asdict(event))
            result["event"] = asdict(event)
        return result

    @app.get("/sessions/{session_id}")
    def get_session(session_id: str) -> dict[str, Any]:
        return _require_session(state, session_id)

    @app.post("/sessions/{session_id}/loop/start")
    def start_loop(session_id: str) -> dict[str, Any]:
        session = _require_session(state, session_id)
        task = _require_task(state, session["task_id"])
        events = adapter.build_context_and_outline(
            task_id=task["id"],
            session_id=session_id,
            workspace_root=Path(task["workspace_root"]),
        )
        _append_events(state, session_id, events)
        session["status"] = "await_outline_approval"
        state.save_session(session)
        return {"session_id": session_id, "next_state": "await_outline_approval", "event_count": len(events)}

    @app.post("/sessions/{session_id}/outline/approve")
    def approve_outline(session_id: str, request: ApproveOutlineRequest) -> dict[str, Any]:
        session = _require_session(state, session_id)
        task = _require_task(state, session["task_id"])
        events = adapter.approve_outline_and_draft(
            task_id=task["id"],
            session_id=session_id,
            workspace_root=Path(task["workspace_root"]),
            outline_markdown=request.outline_markdown,
        )
        _append_events(state, session_id, events)
        session["status"] = "draft_ready"
        state.save_session(session)
        return {"session_id": session_id, "next_state": "draft_ready", "event_count": len(events)}

    @app.post("/sessions/{session_id}/revision/selection")
    def revise_selection(session_id: str, request: ReviseSelectionRequest) -> dict[str, Any]:
        session = _require_session(state, session_id)
        task = _require_task(state, session["task_id"])
        try:
            events = adapter.revise_selection(
                task_id=task["id"],
                session_id=session_id,
                workspace_root=Path(task["workspace_root"]),
                selected_text=request.selected_text,
                instruction=request.instruction,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail="Draft does not exist. Approve the outline first.") from exc
        _append_events(state, session_id, events)
        return {"session_id": session_id, "paths": _event_paths(events)}

    @app.post("/sessions/{session_id}/checklist/run")
    def run_checklist(session_id: str) -> dict[str, Any]:
        session = _require_session(state, session_id)
        task = _require_task(state, session["task_id"])
        events = adapter.run_checklist(
            task_id=task["id"],
            session_id=session_id,
            workspace_root=Path(task["workspace_root"]),
        )
        _append_events(state, session_id, events)
        return {"session_id": session_id, "paths": _event_paths(events)}

    @app.post("/sessions/{session_id}/artifacts/export-markdown")
    def export_markdown(session_id: str) -> dict[str, Any]:
        session = _require_session(state, session_id)
        task = _require_task(state, session["task_id"])
        events = adapter.export_markdown(
            task_id=task["id"],
            session_id=session_id,
            workspace_root=Path(task["workspace_root"]),
        )
        _append_events(state, session_id, events)
        return {"session_id": session_id, "artifact_path": "artifacts/prd-draft.md", "event_count": len(events)}

    @app.post("/sessions/{session_id}/messages")
    def send_message(session_id: str, request: SendMessageRequest) -> dict[str, Any]:
        session = _require_session(state, session_id)
        task = _require_task(state, session["task_id"])
        events = adapter.send_message(
            task_id=task["id"],
            session_id=session_id,
            workspace_root=Path(task["workspace_root"]),
            message=request.message,
        )
        _append_events(state, session_id, events)
        return {"session_id": session_id, "event_count": len(events)}

    @app.get("/sessions/{session_id}/timeline")
    def get_timeline(session_id: str) -> list[dict[str, Any]]:
        if state.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return state.list_timeline_events(session_id)

    return app


def _require_task(state: DocAgentState, task_id: str) -> dict[str, Any]:
    task = state.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def _require_session(state: DocAgentState, session_id: str) -> dict[str, Any]:
    session = state.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def _append_events(state: DocAgentState, session_id: str, events: list[SemanticTimelineEvent]) -> None:
    for event in events:
        state.append_timeline_event(session_id, asdict(event))


def _manual_event(
    task_id: str,
    session_id: str,
    suffix: str,
    actor: TimelineActor,
    kind: SemanticEventKind,
    summary: str,
    paths: list[str],
) -> SemanticTimelineEvent:
    return SemanticTimelineEvent(
        id=f"{task_id}-{suffix}",
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


def _event_paths(events: list[SemanticTimelineEvent]) -> list[str]:
    return [path for event in events for path in event.paths]


app = create_app()
