from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from docagent_api.doctypes import get_doc_type, list_doc_types
from docagent_api.drafts import read_draft, write_draft
from docagent_api.state import DocAgentState
from docagent_mock_runtime.adapter import MockRuntimeAdapter
from docagent_workspace import create_workspace


class CreateTaskRequest(BaseModel):
    doc_type_id: str
    brief: str


class SendMessageRequest(BaseModel):
    message: str


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
        files = [
            path.relative_to(workspace_root).as_posix()
            for path in sorted(workspace_root.rglob("*"))
            if path.is_file()
        ]
        return {"task_id": task_id, "root": str(workspace_root), "files": files}

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

    @app.get("/sessions/{session_id}")
    def get_session(session_id: str) -> dict[str, Any]:
        session = state.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return session

    @app.post("/sessions/{session_id}/messages")
    def send_message(session_id: str, request: SendMessageRequest) -> dict[str, Any]:
        session = state.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        task = _require_task(state, session["task_id"])
        events = adapter.send_message(
            task_id=task["id"],
            session_id=session_id,
            workspace_root=Path(task["workspace_root"]),
            message=request.message,
        )
        for event in events:
            state.append_timeline_event(session_id, asdict(event))
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


app = create_app()
