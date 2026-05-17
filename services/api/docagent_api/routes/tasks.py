from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from docagent_conversion import ConversionLayout, convert_resource_bytes
from docagent_api.doctypes import get_doc_type, is_valid_doc_type_id
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
from docagent_api.session_state import RUNNING_STATES
from docagent_api.state import DocAgentState
from docagent_api.time import utc_now
from docagent_api.workspace_files import list_workspace_files, read_workspace_text_file
from docagent_contracts import RuntimeSessionState, SemanticEventKind, TimelineActor
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
        if not is_valid_doc_type_id(request.doc_type_id):
            raise HTTPException(status_code=404, detail="Document type not found")
        pack_version = (
            state.get_skill_pack_version(request.pack_version_id)
            if request.pack_version_id
            else state.get_latest_skill_pack_version(request.doc_type_id)
        )
        if request.pack_version_id and pack_version is None:
            raise HTTPException(status_code=404, detail="Published skill pack version not found")
        legacy_doc_type = get_doc_type(root / "doc-types", request.doc_type_id) if pack_version is None else None
        if pack_version is None and legacy_doc_type is None:
            raise HTTPException(status_code=404, detail="Published skill pack version not found")
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
            "pack_version_id": pack_version["id"] if pack_version else None,
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
        if not request.force:
            running_sessions = [
                session for session in state.list_sessions_by_task(task_id)
                if session["status"] in RUNNING_STATES
            ]
            if running_sessions:
                raise HTTPException(
                    status_code=409,
                    detail="Cannot update draft while a runtime session is running.",
                )
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
            pack_version = state.get_skill_pack_version(task.get("pack_version_id"))
            skill_path = Path(pack_version["snapshot_path"]) / "SKILL.md" if pack_version else None
            prompt_bundle = build_prompt_bundle(
                root,
                Path(task["workspace_root"]),
                task["id"],
                session_id,
                task["doc_type_id"],
                task.get("pack_version_id"),
                skill_path,
            )
        except FileNotFoundError as exc:
            state.delete_session(session_id)
            raise HTTPException(
                status_code=422,
                detail=f"Cannot create session: missing skill or system prompt file — {exc}",
            ) from exc
        try:
            result = adapter.create_session(session_id, prompt_bundle)
        except Exception as exc:
            state.delete_session(session_id)
            raise HTTPException(status_code=502, detail=f"Runtime session creation failed: {exc}") from exc
        append_runtime_result(state, task["id"], session_id, result)
        return record

    @router.get("/tasks/{task_id}/sessions", response_model=list[SessionResponse])
    def list_task_sessions(task_id: str) -> list[dict[str, Any]]:
        require_task(state, task_id)
        return state.list_sessions_by_task(task_id)

    @router.post("/tasks/{task_id}/inputs/text", response_model=ImportedInputResponse)
    def add_text_input(task_id: str, request: ImportTextRequest) -> dict[str, Any]:
        task = require_task(state, task_id)
        result = import_text_input(
            Path(task["workspace_root"]),
            request.name,
            request.content,
            utc_now(),
        )
        sessions = state.list_sessions_by_task(task_id)
        if sessions:
            latest = max(sessions, key=lambda s: s.get("updated_at", ""))
            event = manual_event(
                task_id,
                latest["id"],
                f"convert-input-{result['id']}",
                TimelineActor.SYSTEM,
                SemanticEventKind.CONVERT_INPUT,
                "Convert input to Markdown",
                [path for path in [result.get("markdown_path"), result["conversion_report_path"]] if path],
            )
            state.append_timeline_event(latest["id"], asdict(event))
            result["event"] = asdict(event)
        return result

    @router.post("/tasks/{task_id}/inputs/files", response_model=ImportedInputResponse)
    async def add_file_input(task_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
        task = require_task(state, task_id)
        content = await file.read()
        result = convert_resource_bytes(
            ConversionLayout(
                root=Path(task["workspace_root"]),
                original_dir="inputs/original",
                markdown_dir="inputs/markdown",
                assets_dir="inputs/assets",
                reports_dir="inputs/reports",
            ),
            original_filename=file.filename or "upload.bin",
            content=content,
            mime_type=file.content_type or "application/octet-stream",
            created_at=utc_now(),
        )
        sessions = state.list_sessions_by_task(task_id)
        if sessions:
            latest = max(sessions, key=lambda s: s.get("updated_at", ""))
            event = manual_event(
                task_id,
                latest["id"],
                f"convert-input-{result['id']}",
                TimelineActor.SYSTEM,
                SemanticEventKind.CONVERT_INPUT,
                "Convert input to Markdown",
                [path for path in [result.get("markdown_path"), result["conversion_report_path"]] if path],
            )
            state.append_timeline_event(latest["id"], asdict(event))
            result["event"] = asdict(event)
        return result

    return router
