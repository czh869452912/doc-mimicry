from __future__ import annotations

from dataclasses import asdict
import os
from pathlib import Path
from threading import Thread
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from docagent_api.doctypes import get_doc_type, list_doc_types
from docagent_api.response_models import (
    DocTypeSummaryResponse,
    DraftResponse,
    HealthResponse,
    ImportedInputResponse,
    LoopActionResponse,
    SessionResponse,
    TaskResponse,
    TimelineEventResponse,
    WorkspaceFileContentResponse,
    WorkspaceResponse,
)
from docagent_api.drafts import read_draft, write_draft
from docagent_api.imports import import_text_input
from docagent_api.prompts import build_prompt_bundle
from docagent_api.runtime_factory import create_runtime_adapter
from docagent_api.session_state import InvalidSessionTransition, require_transition
from docagent_api.state import DocAgentState
from docagent_api.time import utc_now
from docagent_api.workspace_files import list_workspace_files, read_workspace_text_file
from docagent_contracts import (
    RuntimeKind,
    RuntimeOperationResult,
    RuntimeSessionState,
    SemanticEventKind,
    SemanticTimelineEvent,
    TimelineActor,
    TimelineStatus,
)
from docagent_timeline import map_openhands_raw_event
from docagent_workspace import create_workspace


class CreateTaskRequest(BaseModel):
    doc_type_id: str
    brief: str | None = None
    title: str | None = None
    description: str | None = None


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


def create_app(
    state_root: Path | None = None,
    repo_root: Path | None = None,
    runtime_name: str | None = None,
    runtime_adapter: Any | None = None,
) -> FastAPI:
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
    _recover_interrupted_sessions(state)
    adapter = runtime_adapter or create_runtime_adapter(runtime_name)

    @app.get("/health", response_model=HealthResponse)
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/doc-types", response_model=list[DocTypeSummaryResponse])
    def doc_types() -> list[dict[str, Any]]:
        return list_doc_types(root / "doc-types")

    @app.get("/doc-types/{doc_type_id}", response_model=DocTypeSummaryResponse)
    def doc_type_detail(doc_type_id: str) -> dict[str, Any]:
        detail = get_doc_type(root / "doc-types", doc_type_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Document type not found")
        return detail

    @app.get("/tasks", response_model=list[TaskResponse])
    def list_tasks() -> list[dict[str, Any]]:
        return state.list_tasks()

    @app.post("/tasks", response_model=TaskResponse)
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

    @app.get("/tasks/{task_id}", response_model=TaskResponse)
    def get_task(task_id: str) -> dict[str, Any]:
        return _require_task(state, task_id)

    @app.get("/tasks/{task_id}/workspace", response_model=WorkspaceResponse)
    def get_workspace(task_id: str) -> dict[str, Any]:
        task = _require_task(state, task_id)
        workspace_root = Path(task["workspace_root"])
        return {"task_id": task_id, "root": str(workspace_root), "files": list_workspace_files(workspace_root)}

    @app.get("/tasks/{task_id}/workspace/files", response_model=WorkspaceFileContentResponse)
    def get_workspace_file(task_id: str, file_path: str = Query(alias="path")) -> dict[str, str]:
        task = _require_task(state, task_id)
        try:
            content = read_workspace_text_file(Path(task["workspace_root"]), file_path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Workspace file not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"path": file_path, "content": content}

    @app.get("/tasks/{task_id}/draft", response_model=DraftResponse)
    def get_draft(task_id: str) -> dict[str, str]:
        task = _require_task(state, task_id)
        return {"task_id": task_id, "markdown": read_draft(Path(task["workspace_root"]))}

    @app.put("/tasks/{task_id}/draft", response_model=DraftResponse)
    def update_draft(task_id: str, request: UpdateDraftRequest) -> dict[str, str]:
        task = _require_task(state, task_id)
        write_draft(Path(task["workspace_root"]), request.markdown)
        return {"task_id": task_id, "markdown": read_draft(Path(task["workspace_root"]))}

    @app.post("/tasks/{task_id}/sessions", response_model=SessionResponse)
    def create_session(task_id: str) -> dict[str, Any]:
        task = _require_task(state, task_id)
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
        prompt_bundle = build_prompt_bundle(
            root,
            Path(task["workspace_root"]),
            task["id"],
            session_id,
            task["doc_type_id"],
        )
        result = adapter.create_session(session_id, prompt_bundle)
        _append_runtime_result(state, task["id"], session_id, result)
        return record

    @app.get("/tasks/{task_id}/sessions", response_model=list[SessionResponse])
    def list_task_sessions(task_id: str) -> list[dict[str, Any]]:
        _require_task(state, task_id)
        return [session for session in state.list_sessions() if session["task_id"] == task_id]

    @app.post("/tasks/{task_id}/inputs/text", response_model=ImportedInputResponse)
    def add_text_input(task_id: str, request: ImportTextRequest) -> dict[str, Any]:
        task = _require_task(state, task_id)
        result = import_text_input(
            Path(task["workspace_root"]),
            request.name,
            request.content,
            utc_now(),
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

    @app.get("/sessions/{session_id}", response_model=SessionResponse)
    def get_session(session_id: str) -> dict[str, Any]:
        return _require_session(state, session_id)

    @app.post("/sessions/{session_id}/loop/start", response_model=LoopActionResponse)
    def start_loop(
        session_id: str,
        response: Response,
        background: bool = Query(default=False),
    ) -> dict[str, Any]:
        session = _require_session(state, session_id)
        task = _require_task(state, session["task_id"])
        if background:
            operation = _stream_or_sync(
                adapter,
                "start_loop_stream",
                lambda: adapter.start_loop(session_id),
                lambda stream_method: lambda: stream_method(
                    session_id,
                    _runtime_event_sink(state, task["id"], session_id),
                ),
            )
            response.status_code = 202
            return _start_background_runtime_operation(
                state,
                task["id"],
                session,
                RuntimeSessionState.RUNNING_CONTEXT,
                operation,
            )
        result = _run_runtime_operation(
            state,
            session,
            RuntimeSessionState.RUNNING_CONTEXT,
            lambda: adapter.start_loop(session_id),
        )
        _append_runtime_result(state, task["id"], session_id, result)
        _set_session_state(state, session, result.next_state)
        return _runtime_result_response(result)

    @app.post("/sessions/{session_id}/outline/approve", response_model=LoopActionResponse)
    def approve_outline(
        session_id: str,
        request: ApproveOutlineRequest,
        response: Response,
        background: bool = Query(default=False),
    ) -> dict[str, Any]:
        session = _require_session(state, session_id)
        task = _require_task(state, session["task_id"])
        _prepare_transition(state, session, RuntimeSessionState.RUNNING_DRAFT)
        (Path(task["workspace_root"]) / "draft" / "outline.md").write_text(
            request.outline_markdown if request.outline_markdown.endswith("\n") else f"{request.outline_markdown}\n",
            encoding="utf-8",
        )
        if background:
            operation = _stream_or_sync(
                adapter,
                "approve_outline_stream",
                lambda: adapter.approve_outline(session_id),
                lambda stream_method: lambda: stream_method(
                    session_id,
                    _runtime_event_sink(state, task["id"], session_id),
                ),
            )
            response.status_code = 202
            return _start_background_runtime_operation(
                state,
                task["id"],
                session,
                RuntimeSessionState.RUNNING_DRAFT,
                operation,
                previous_state_on_failure=RuntimeSessionState.AWAIT_OUTLINE_APPROVAL,
                transition_prepared=True,
            )
        try:
            result = adapter.approve_outline(session_id)
        except Exception as exc:
            _set_session_state(state, session, RuntimeSessionState.AWAIT_OUTLINE_APPROVAL)
            raise HTTPException(status_code=502, detail=f"Runtime operation failed: {exc}") from exc
        _append_runtime_result(state, task["id"], session_id, result)
        _set_session_state(state, session, result.next_state)
        return _runtime_result_response(result)

    @app.post("/sessions/{session_id}/revision/selection", response_model=LoopActionResponse)
    def revise_selection(
        session_id: str,
        request: ReviseSelectionRequest,
        response: Response,
        background: bool = Query(default=False),
    ) -> dict[str, Any]:
        session = _require_session(state, session_id)
        task = _require_task(state, session["task_id"])
        previous_state = RuntimeSessionState(session["status"])
        try:
            _prepare_transition(state, session, RuntimeSessionState.RUNNING_REVISION)
            if background:
                operation = _stream_or_sync(
                    adapter,
                    "revise_selection_stream",
                    lambda: adapter.revise_selection(session_id, request.selected_text, request.instruction),
                    lambda stream_method: lambda: stream_method(
                        session_id,
                        request.selected_text,
                        request.instruction,
                        _runtime_event_sink(state, task["id"], session_id),
                    ),
                )
                response.status_code = 202
                return _start_background_runtime_operation(
                    state,
                    task["id"],
                    session,
                    RuntimeSessionState.RUNNING_REVISION,
                    operation,
                    previous_state_on_failure=previous_state,
                    transition_prepared=True,
                )
            result = adapter.revise_selection(session_id, request.selected_text, request.instruction)
        except HTTPException:
            raise
        except FileNotFoundError as exc:
            _set_session_state(state, session, previous_state)
            raise HTTPException(status_code=400, detail="Draft does not exist. Approve the outline first.") from exc
        except ValueError as exc:
            _set_session_state(state, session, previous_state)
            raise HTTPException(status_code=422, detail="Selected text not found in draft.") from exc
        except Exception as exc:
            _set_session_state(state, session, previous_state)
            raise HTTPException(status_code=502, detail=f"Runtime operation failed: {exc}") from exc
        _append_runtime_result(state, task["id"], session_id, result)
        _set_session_state(state, session, result.next_state)
        return {"session_id": session_id, "paths": result.changed_paths}

    @app.post("/sessions/{session_id}/checklist/run", response_model=LoopActionResponse)
    def run_checklist(
        session_id: str,
        response: Response,
        background: bool = Query(default=False),
    ) -> dict[str, Any]:
        session = _require_session(state, session_id)
        task = _require_task(state, session["task_id"])
        if background:
            operation = _stream_or_sync(
                adapter,
                "run_checklist_stream",
                lambda: adapter.run_checklist(session_id),
                lambda stream_method: lambda: stream_method(
                    session_id,
                    _runtime_event_sink(state, task["id"], session_id),
                ),
            )
            response.status_code = 202
            return _start_background_runtime_operation(
                state,
                task["id"],
                session,
                RuntimeSessionState.RUNNING_CHECKLIST,
                operation,
            )
        result = _run_runtime_operation(
            state,
            session,
            RuntimeSessionState.RUNNING_CHECKLIST,
            lambda: adapter.run_checklist(session_id),
        )
        _append_runtime_result(state, task["id"], session_id, result)
        _set_session_state(state, session, result.next_state)
        return {"session_id": session_id, "paths": result.changed_paths}

    @app.post("/sessions/{session_id}/artifacts/export-markdown", response_model=LoopActionResponse)
    def export_markdown(
        session_id: str,
        response: Response,
        background: bool = Query(default=False),
    ) -> dict[str, Any]:
        session = _require_session(state, session_id)
        task = _require_task(state, session["task_id"])
        if background:
            operation = _stream_or_sync(
                adapter,
                "export_markdown_stream",
                lambda: adapter.export_markdown(session_id),
                lambda stream_method: lambda: stream_method(
                    session_id,
                    _runtime_event_sink(state, task["id"], session_id),
                ),
            )
            response.status_code = 202
            return _start_background_runtime_operation(
                state,
                task["id"],
                session,
                RuntimeSessionState.RUNNING_EXPORT,
                operation,
            )
        result = _run_runtime_operation(
            state,
            session,
            RuntimeSessionState.RUNNING_EXPORT,
            lambda: adapter.export_markdown(session_id),
        )
        _append_runtime_result(state, task["id"], session_id, result)
        _set_session_state(state, session, result.next_state)
        return {"session_id": session_id, "artifact_path": "artifacts/prd-draft.md", "event_count": len(result.events)}

    @app.post("/sessions/{session_id}/messages", response_model=LoopActionResponse)
    def send_message(
        session_id: str,
        request: SendMessageRequest,
        response: Response,
        background: bool = Query(default=False),
    ) -> dict[str, Any]:
        session = _require_session(state, session_id)
        task = _require_task(state, session["task_id"])
        if background:
            user_event = _manual_event(
                task["id"], session_id, f"user-{uuid4().hex[:8]}",
                TimelineActor.USER, SemanticEventKind.USER_MESSAGE,
                request.message, [],
            )
            state.append_timeline_event(session_id, asdict(user_event))
            stream_method = getattr(adapter, "send_message_stream", None)
            if callable(stream_method):
                operation = lambda: stream_method(
                    session_id,
                    request.message,
                    _runtime_event_sink(state, task["id"], session_id),
                )
            else:
                operation = lambda: adapter.send_message(session_id, request.message)
            response.status_code = 202
            return _start_background_runtime_operation(
                state,
                task["id"],
                session,
                RuntimeSessionState.RUNNING_CHAT,
                operation,
            )
        result = _run_runtime_operation(
            state,
            session,
            RuntimeSessionState.RUNNING_CHAT,
            lambda: adapter.send_message(session_id, request.message),
        )
        _append_runtime_result(state, task["id"], session_id, result)
        # Adapters that return no semantic events (e.g. OpenHands) don't record the user
        # message themselves — add it explicitly so it always appears in the timeline.
        if not result.events:
            user_event = _manual_event(
                task["id"], session_id, f"user-{uuid4().hex[:8]}",
                TimelineActor.USER, SemanticEventKind.USER_MESSAGE,
                request.message, [],
            )
            state.append_timeline_event(session_id, asdict(user_event))
        _set_session_state(state, session, result.next_state)
        return {"session_id": session_id, "event_count": len(result.events)}

    @app.post("/sessions/{session_id}/cancel", response_model=LoopActionResponse)
    def cancel_session(session_id: str) -> dict[str, Any]:
        session = _require_session(state, session_id)
        task = _require_task(state, session["task_id"])
        previous_state = RuntimeSessionState(session["status"])
        _prepare_transition(state, session, RuntimeSessionState.CANCELLED)
        try:
            result = adapter.cancel(session_id)
        except HTTPException:
            _set_session_state(state, session, previous_state)
            raise
        except Exception as exc:
            _set_session_state(state, session, previous_state)
            raise HTTPException(status_code=502, detail=f"Runtime cancel failed: {exc}") from exc
        _append_runtime_result(state, task["id"], session_id, result)
        # result.next_state is expected to be CANCELLED; _set_session_state picks up
        # any adapter-provided next_state (e.g. to capture timestamps or sub-states).
        _set_session_state(state, session, result.next_state)
        return _runtime_result_response(result)

    @app.get("/sessions/{session_id}/timeline", response_model=list[TimelineEventResponse])
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


def _title_from_description(description: str) -> str:
    first_line = next((line.strip() for line in description.splitlines() if line.strip()), "Untitled workspace")
    return first_line[:80]


def _require_session(state: DocAgentState, session_id: str) -> dict[str, Any]:
    session = state.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def _append_events(state: DocAgentState, session_id: str, events: list[SemanticTimelineEvent]) -> None:
    for event in events:
        state.append_timeline_event(session_id, asdict(event))


def _append_runtime_result(
    state: DocAgentState,
    task_id: str,
    session_id: str,
    result: RuntimeOperationResult,
) -> None:
    _append_events(state, session_id, result.events)
    for raw_event in result.raw_events:
        state.append_raw_runtime_event(session_id, raw_event)
        if raw_event.runtime is RuntimeKind.OPENHANDS:
            semantic = map_openhands_raw_event(raw_event, task_id)
            if semantic is not None:
                state.append_timeline_event(session_id, asdict(semantic))


def _prepare_transition(
    state: DocAgentState,
    session: dict[str, Any],
    next_state: RuntimeSessionState,
) -> None:
    try:
        require_transition(session["status"], next_state)
    except InvalidSessionTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _set_session_state(state, session, next_state)


def _recover_interrupted_sessions(state: DocAgentState) -> None:
    running_states = {
        RuntimeSessionState.RUNNING_CONTEXT.value,
        RuntimeSessionState.RUNNING_DRAFT.value,
        RuntimeSessionState.RUNNING_REVISION.value,
        RuntimeSessionState.RUNNING_CHAT.value,
        RuntimeSessionState.RUNNING_CHECKLIST.value,
        RuntimeSessionState.RUNNING_EXPORT.value,
    }
    for session in state.list_sessions():
        if session["status"] in running_states:
            _set_session_state(state, session, RuntimeSessionState.FAILED)


def _run_runtime_operation(
    state: DocAgentState,
    session: dict[str, Any],
    running_state: RuntimeSessionState,
    operation: Any,
) -> RuntimeOperationResult:
    previous_state = RuntimeSessionState(session["status"])
    _prepare_transition(state, session, running_state)
    try:
        return operation()
    except HTTPException:
        raise
    except Exception as exc:
        _set_session_state(state, session, previous_state)
        raise HTTPException(status_code=502, detail=f"Runtime operation failed: {exc}") from exc


def _start_background_runtime_operation(
    state: DocAgentState,
    task_id: str,
    session: dict[str, Any],
    running_state: RuntimeSessionState,
    operation: Any,
    previous_state_on_failure: RuntimeSessionState | None = None,
    transition_prepared: bool = False,
) -> dict[str, Any]:
    previous_state = previous_state_on_failure or RuntimeSessionState(session["status"])
    if not transition_prepared:
        _prepare_transition(state, session, running_state)

    def worker() -> None:
        try:
            result = operation()
        except Exception as exc:
            failure = _manual_event(
                task_id,
                session["id"],
                f"runtime-failed-{uuid4().hex[:8]}",
                TimelineActor.SYSTEM,
                SemanticEventKind.ERROR,
                f"Runtime operation failed: {exc}",
                [],
                status=TimelineStatus.FAILED,
            )
            state.append_timeline_event(session["id"], asdict(failure))
            _set_session_state(state, session, previous_state)
            return
        _append_runtime_result(state, task_id, session["id"], result)
        _set_session_state(state, session, result.next_state)

    Thread(target=worker, daemon=True).start()
    return {"session_id": session["id"], "accepted": True, "status": running_state.value}


def _runtime_event_sink(state: DocAgentState, task_id: str, session_id: str) -> Any:
    def sink(raw_event: Any) -> None:
        state.append_raw_runtime_event(session_id, raw_event)
        if raw_event.runtime is RuntimeKind.OPENHANDS:
            semantic = map_openhands_raw_event(raw_event, task_id)
            if semantic is not None:
                state.append_timeline_event(session_id, asdict(semantic))

    return sink


def _stream_or_sync(adapter: Any, stream_name: str, sync_operation: Any, stream_operation: Any) -> Any:
    stream_method = getattr(adapter, stream_name, None)
    if callable(stream_method):
        return stream_operation(stream_method)
    return sync_operation


def _set_session_state(
    state: DocAgentState,
    session: dict[str, Any],
    next_state: RuntimeSessionState,
) -> None:
    session["status"] = next_state.value
    session["updated_at"] = utc_now()
    state.save_session(session)


def _manual_event(
    task_id: str,
    session_id: str,
    suffix: str,
    actor: TimelineActor,
    kind: SemanticEventKind,
    summary: str,
    paths: list[str],
    status: TimelineStatus = TimelineStatus.SUCCEEDED,
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
        status=status,
        created_at=utc_now(),
    )


def _event_paths(events: list[SemanticTimelineEvent]) -> list[str]:
    return [path for event in events for path in event.paths]


def _runtime_result_response(result: RuntimeOperationResult) -> dict[str, Any]:
    return {
        "session_id": result.session_id,
        "next_state": result.next_state.value,
        "event_count": len(result.events),
        "raw_event_count": len(result.raw_events),
    }


def state_root_from_env() -> Path | None:
    value = os.environ.get("DOCAGENT_STATE_ROOT")
    return Path(value) if value else None


app = create_app(state_root=state_root_from_env())
