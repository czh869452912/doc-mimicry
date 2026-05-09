from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from docagent_api.doctypes import get_doc_type
from docagent_api.drafts import read_draft, write_draft
from docagent_api.imports import import_text_input
from docagent_api.prompts import build_prompt_bundle
from docagent_api.request_models import CreateTaskRequest, ImportTextRequest, UpdateDraftRequest
from docagent_api.response_models import (
    DraftResponse,
    ImportedInputResponse,
    SessionResponse,
    TaskResponse,
    WorkspaceFileContentResponse,
    WorkspaceResponse,
)
from docagent_api.routes._shared import (
    append_runtime_result,
    manual_event,
    require_task,
)
from docagent_api.state import DocAgentState
from docagent_api.time import utc_now
from docagent_api.workspace_files import list_workspace_files, read_workspace_text_file
from docagent_contracts import SemanticEventKind, TimelineActor
from docagent_workspace import create_workspace


def _title_from_description(description: str) -> str:
    first_line = next((line.strip() for line in description.splitlines() if line.strip()), "Untitled workspace")
    return first_line[:80]


def create_tasks_router(state: DocAgentState, adapter: Any, root: Path) -> APIRouter:
    router = APIRouter()

    @router.get("/tasks", response_model=list[TaskResponse])
    def list_tasks() -> list[dict[str, Any]]:
        return state.list_tasks()

    @router.post("/tasks", response_model=TaskResponse)
    def create_task(request: CreateTaskRequest) -> dict[str, Any]:
        if get_doc_type(root / "doc-types", request.doc_type_id) is None:
            raise HTTPException(status_code=404, detail="Document type not found")
        description = (request.description or request.brief or "").strip()
        if not description:
            raise HTTPException(status_code=422, detail="Description is required")
        title = (request.title or _title_from_description(description)).strip()
        task_id = f"task-{uuid4().hex[:8]}"
        workspace_root = state.workspace_root(task_id)
        create_workspace(workspace_root, description)
        created_at = utc_now()
        record = {
            "id": task_id,
            "doc_type_id": request.doc_type_id,
            "brief": description,
            "title": title,
            "description": description,
            "workspace_root": str(workspace_root),
            "created_at": created_at,
            "updated_at": created_at,
        }
        state.save_task(record)
        return record

    @router.get("/tasks/{task_id}", response_model=TaskResponse)
    def get_task(task_id: str) -> dict[str, Any]:
        return require_task(state, task_id)

    @router.get("/tasks/{task_id}/workspace", response_model=WorkspaceResponse)
    def get_workspace(task_id: str) -> dict[str, Any]:
        task = require_task(state, task_id)
        workspace_root = Path(task["workspace_root"])
        return {"task_id": task_id, "root": str(workspace_root), "files": list_workspace_files(workspace_root)}

    @router.get("/tasks/{task_id}/workspace/files", response_model=WorkspaceFileContentResponse)
    def get_workspace_file(task_id: str, file_path: str = Query(alias="path")) -> dict[str, str]:
        task = require_task(state, task_id)
        try:
            content = read_workspace_text_file(Path(task["workspace_root"]), file_path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Workspace file not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"path": file_path, "content": content}

    @router.get("/tasks/{task_id}/draft", response_model=DraftResponse)
    def get_draft(task_id: str) -> dict[str, str]:
        task = require_task(state, task_id)
        return {"task_id": task_id, "markdown": read_draft(Path(task["workspace_root"]))}

    @router.put("/tasks/{task_id}/draft", response_model=DraftResponse)
    def update_draft(task_id: str, request: UpdateDraftRequest) -> dict[str, str]:
        task = require_task(state, task_id)
        write_draft(Path(task["workspace_root"]), request.markdown)
        return {"task_id": task_id, "markdown": read_draft(Path(task["workspace_root"]))}

    @router.post("/tasks/{task_id}/sessions", response_model=SessionResponse)
    def create_session(task_id: str) -> dict[str, Any]:
        task = require_task(state, task_id)
        session_id = f"session-{uuid4().hex[:8]}"
        created_at = utc_now()
        record = {
            "id": session_id,
            "task_id": task_id,
            "status": "idle",
            "created_at": created_at,
            "updated_at": created_at,
        }
        state.save_session(record)
        try:
            prompt_bundle = build_prompt_bundle(
                root,
                Path(task["workspace_root"]),
                task["id"],
                session_id,
                task["doc_type_id"],
            )
        except FileNotFoundError as exc:
            state.delete_session(session_id)
            raise HTTPException(
                status_code=422,
                detail=f"Cannot create session: missing skill or system prompt file — {exc}",
            ) from exc
        result = adapter.create_session(session_id, prompt_bundle)
        append_runtime_result(state, task["id"], session_id, result)
        return record

    @router.get("/tasks/{task_id}/sessions", response_model=list[SessionResponse])
    def list_task_sessions(task_id: str) -> list[dict[str, Any]]:
        require_task(state, task_id)
        return [s for s in state.list_sessions() if s["task_id"] == task_id]

    @router.post("/tasks/{task_id}/inputs/text", response_model=ImportedInputResponse)
    def add_text_input(task_id: str, request: ImportTextRequest) -> dict[str, Any]:
        task = require_task(state, task_id)
        result = import_text_input(
            Path(task["workspace_root"]),
            request.name,
            request.content,
            utc_now(),
        )
        sessions = [s for s in state.list_sessions() if s["task_id"] == task_id]
        if sessions:
            latest = max(sessions, key=lambda s: s.get("updated_at", ""))
            event = manual_event(
                task_id,
                latest["id"],
                f"convert-input-{result['id']}",
                TimelineActor.SYSTEM,
                SemanticEventKind.CONVERT_INPUT,
                "Convert input to Markdown",
                [result["markdown_path"], result["conversion_report_path"]],
            )
            state.append_timeline_event(latest["id"], asdict(event))
            result["event"] = asdict(event)
        return result

    return router
