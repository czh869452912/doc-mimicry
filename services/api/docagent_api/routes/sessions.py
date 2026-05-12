from __future__ import annotations

import asyncio
import json as _json
import logging
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse

from docagent_api.background import BackgroundRuntimeRunner
from docagent_api.celery_app import celery_app
from docagent_api.request_models import (
    ApproveOutlineRequest,
    ReviseSelectionRequest,
    SendMessageRequest,
)
from docagent_api.response_models import LoopActionResponse, SessionResponse, TimelineEventResponse
from docagent_api.routes._shared import (
    append_runtime_result,
    manual_event,
    prepare_transition,
    require_session,
    require_task,
    run_runtime_operation,
    runtime_event_sink,
    runtime_result_response,
    set_session_state,
    start_background_runtime_operation,
    stream_or_sync,
)
from docagent_api.state import DocAgentState
from docagent_contracts import RuntimeSessionState, SemanticEventKind, TimelineActor

logger = logging.getLogger(__name__)


def create_sessions_router(state: DocAgentState, adapter: Any, runner: BackgroundRuntimeRunner) -> APIRouter:
    router = APIRouter()

    @router.get("/sessions/{session_id}", response_model=SessionResponse)
    def get_session(session_id: str) -> dict[str, Any]:
        return require_session(state, session_id)

    @router.post("/sessions/{session_id}/loop/start", response_model=LoopActionResponse)
    def start_loop(
        session_id: str,
        response: Response,
        background: bool = Query(default=False),
    ) -> dict[str, Any]:
        session = require_session(state, session_id)
        task = require_task(state, session["task_id"])
        if background:
            operation = stream_or_sync(
                adapter,
                "start_loop_stream",
                lambda: adapter.start_loop(session_id),
                lambda m: lambda: m(session_id, runtime_event_sink(state, task["id"], session_id)),
            )
            response.status_code = 202
            return start_background_runtime_operation(
                state,
                task["id"],
                session,
                RuntimeSessionState.RUNNING_CONTEXT,
                operation,
                runner,
                operation_name="start_loop_stream" if callable(getattr(adapter, "start_loop_stream", None)) else "start_loop",
            )
        result = run_runtime_operation(
            state, session, RuntimeSessionState.RUNNING_CONTEXT, lambda: adapter.start_loop(session_id),
            task_id=task["id"],
        )
        append_runtime_result(state, task["id"], session_id, result)
        set_session_state(state, session, result.next_state, task_id=task["id"])
        return runtime_result_response(result)

    @router.post("/sessions/{session_id}/outline/approve", response_model=LoopActionResponse)
    def approve_outline(
        session_id: str,
        request: ApproveOutlineRequest,
        response: Response,
        background: bool = Query(default=False),
    ) -> dict[str, Any]:
        session = require_session(state, session_id)
        task = require_task(state, session["task_id"])
        prepare_transition(state, session, RuntimeSessionState.RUNNING_DRAFT, task_id=task["id"])
        outline_text = request.outline_markdown
        if not outline_text.endswith("\n"):
            outline_text = f"{outline_text}\n"
        outline_path = Path(task["workspace_root"]) / "draft" / "outline.md"
        outline_path.parent.mkdir(parents=True, exist_ok=True)
        outline_path.write_text(outline_text, encoding="utf-8")
        if background:
            operation = stream_or_sync(
                adapter,
                "approve_outline_stream",
                lambda: adapter.approve_outline(session_id),
                lambda m: lambda: m(session_id, runtime_event_sink(state, task["id"], session_id)),
            )
            response.status_code = 202
            return start_background_runtime_operation(
                state, task["id"], session, RuntimeSessionState.RUNNING_DRAFT, operation,
                runner,
                previous_state_on_failure=RuntimeSessionState.AWAIT_OUTLINE_APPROVAL,
                transition_prepared=True,
                operation_name="approve_outline_stream" if callable(getattr(adapter, "approve_outline_stream", None)) else "approve_outline",
            )
        try:
            result = adapter.approve_outline(session_id)
        except Exception as exc:
            set_session_state(state, session, RuntimeSessionState.AWAIT_OUTLINE_APPROVAL, task_id=task["id"])
            raise HTTPException(status_code=502, detail=f"Runtime operation failed: {exc}") from exc
        append_runtime_result(state, task["id"], session_id, result)
        set_session_state(state, session, result.next_state, task_id=task["id"])
        return runtime_result_response(result)

    @router.post("/sessions/{session_id}/revision/selection", response_model=LoopActionResponse)
    def revise_selection(
        session_id: str,
        request: ReviseSelectionRequest,
        response: Response,
        background: bool = Query(default=False),
    ) -> dict[str, Any]:
        session = require_session(state, session_id)
        task = require_task(state, session["task_id"])
        previous_state = RuntimeSessionState(session["status"])
        try:
            prepare_transition(state, session, RuntimeSessionState.RUNNING_REVISION, task_id=task["id"])
            if background:
                operation = stream_or_sync(
                    adapter,
                    "revise_selection_stream",
                    lambda: adapter.revise_selection(session_id, request.selected_text, request.instruction),
                    lambda m: lambda: m(
                        session_id, request.selected_text, request.instruction,
                        runtime_event_sink(state, task["id"], session_id),
                    ),
                )
                response.status_code = 202
                return start_background_runtime_operation(
                    state, task["id"], session, RuntimeSessionState.RUNNING_REVISION, operation,
                    runner,
                    previous_state_on_failure=previous_state, transition_prepared=True,
                    operation_name=(
                        "revise_selection_stream"
                        if callable(getattr(adapter, "revise_selection_stream", None))
                        else "revise_selection"
                    ),
                    operation_kwargs={
                        "selection": request.selected_text,
                        "instruction": request.instruction,
                    },
                )
            result = adapter.revise_selection(session_id, request.selected_text, request.instruction)
        except HTTPException:
            raise
        except FileNotFoundError as exc:
            set_session_state(state, session, previous_state, task_id=task["id"])
            raise HTTPException(status_code=400, detail="Draft does not exist. Approve the outline first.") from exc
        except ValueError as exc:
            set_session_state(state, session, previous_state, task_id=task["id"])
            raise HTTPException(status_code=422, detail="Selected text not found in draft.") from exc
        except Exception as exc:
            set_session_state(state, session, previous_state, task_id=task["id"])
            raise HTTPException(status_code=502, detail=f"Runtime operation failed: {exc}") from exc
        append_runtime_result(state, task["id"], session_id, result)
        set_session_state(state, session, result.next_state, task_id=task["id"])
        return {"session_id": session_id, "paths": result.changed_paths}

    @router.post("/sessions/{session_id}/checklist/run", response_model=LoopActionResponse)
    def run_checklist(
        session_id: str,
        response: Response,
        background: bool = Query(default=False),
    ) -> dict[str, Any]:
        session = require_session(state, session_id)
        task = require_task(state, session["task_id"])
        if background:
            operation = stream_or_sync(
                adapter,
                "run_checklist_stream",
                lambda: adapter.run_checklist(session_id),
                lambda m: lambda: m(session_id, runtime_event_sink(state, task["id"], session_id)),
            )
            response.status_code = 202
            return start_background_runtime_operation(
                state,
                task["id"],
                session,
                RuntimeSessionState.RUNNING_CHECKLIST,
                operation,
                runner,
                operation_name="run_checklist_stream" if callable(getattr(adapter, "run_checklist_stream", None)) else "run_checklist",
            )
        result = run_runtime_operation(
            state, session, RuntimeSessionState.RUNNING_CHECKLIST, lambda: adapter.run_checklist(session_id),
            task_id=task["id"],
        )
        append_runtime_result(state, task["id"], session_id, result)
        set_session_state(state, session, result.next_state, task_id=task["id"])
        return {"session_id": session_id, "paths": result.changed_paths}

    @router.post("/sessions/{session_id}/artifacts/export-markdown", response_model=LoopActionResponse)
    def export_markdown(
        session_id: str,
        response: Response,
        background: bool = Query(default=False),
    ) -> dict[str, Any]:
        session = require_session(state, session_id)
        task = require_task(state, session["task_id"])
        if background:
            operation = stream_or_sync(
                adapter,
                "export_markdown_stream",
                lambda: adapter.export_markdown(session_id),
                lambda m: lambda: m(session_id, runtime_event_sink(state, task["id"], session_id)),
            )
            response.status_code = 202
            return start_background_runtime_operation(
                state,
                task["id"],
                session,
                RuntimeSessionState.RUNNING_EXPORT,
                operation,
                runner,
                operation_name=(
                    "export_markdown_stream"
                    if callable(getattr(adapter, "export_markdown_stream", None))
                    else "export_markdown"
                ),
            )
        result = run_runtime_operation(
            state, session, RuntimeSessionState.RUNNING_EXPORT, lambda: adapter.export_markdown(session_id),
            task_id=task["id"],
        )
        append_runtime_result(state, task["id"], session_id, result)
        set_session_state(state, session, result.next_state, task_id=task["id"])
        return {"session_id": session_id, "artifact_path": "artifacts/prd-draft.md", "event_count": len(result.events)}

    @router.post("/sessions/{session_id}/messages", response_model=LoopActionResponse)
    def send_message(
        session_id: str,
        request: SendMessageRequest,
        response: Response,
        background: bool = Query(default=False),
    ) -> dict[str, Any]:
        session = require_session(state, session_id)
        task = require_task(state, session["task_id"])
        runtime_message = _message_with_attachments(request)
        if background:
            user_event = manual_event(
                task["id"], session_id, f"user-{uuid4().hex[:8]}",
                TimelineActor.USER, SemanticEventKind.USER_MESSAGE, runtime_message, [],
            )
            state.append_timeline_event(session_id, asdict(user_event))
            stream_method = getattr(adapter, "send_message_stream", None)
            if callable(stream_method):
                operation = lambda: stream_method(
                    session_id, runtime_message,
                    runtime_event_sink(state, task["id"], session_id),
                )
            else:
                operation = lambda: adapter.send_message(session_id, runtime_message)
            response.status_code = 202
            return start_background_runtime_operation(
                state,
                task["id"],
                session,
                RuntimeSessionState.RUNNING_CHAT,
                operation,
                runner,
                operation_name=(
                    "send_message_stream"
                    if callable(getattr(adapter, "send_message_stream", None))
                    else "send_message"
                ),
                operation_kwargs={"message": runtime_message},
            )
        result = run_runtime_operation(
            state, session, RuntimeSessionState.RUNNING_CHAT,
            lambda: adapter.send_message(session_id, runtime_message),
            task_id=task["id"],
        )
        append_runtime_result(state, task["id"], session_id, result)
        if not result.events:
            user_event = manual_event(
                task["id"], session_id, f"user-{uuid4().hex[:8]}",
                TimelineActor.USER, SemanticEventKind.USER_MESSAGE, runtime_message, [],
            )
            state.append_timeline_event(session_id, asdict(user_event))
        set_session_state(state, session, result.next_state, task_id=task["id"])
        return {"session_id": session_id, "event_count": len(result.events)}

    @router.post("/sessions/{session_id}/cancel", response_model=LoopActionResponse)
    def cancel_session(session_id: str) -> dict[str, Any]:
        session = require_session(state, session_id)
        task = require_task(state, session["task_id"])
        previous_state = RuntimeSessionState(session["status"])
        celery_task_id = session.get("celery_task_id")
        if celery_task_id:
            try:
                celery_app.control.revoke(celery_task_id, terminate=True)
            except Exception as exc:
                logger.warning("Failed to revoke Celery task %s during cancel: %s", celery_task_id, exc)
        state.release_operation_lease(session_id, celery_task_id)
        session.pop("celery_task_id", None)
        prepare_transition(state, session, RuntimeSessionState.CANCELLED, task_id=task["id"])
        try:
            result = adapter.cancel(session_id)
        except HTTPException:
            set_session_state(state, session, previous_state, task_id=task["id"])
            raise
        except Exception as exc:
            set_session_state(state, session, previous_state, task_id=task["id"])
            raise HTTPException(status_code=502, detail=f"Runtime cancel failed: {exc}") from exc
        append_runtime_result(state, task["id"], session_id, result)
        set_session_state(state, session, result.next_state, task_id=task["id"])
        return runtime_result_response(result)

    @router.get("/sessions/{session_id}/timeline", response_model=list[TimelineEventResponse])
    def get_timeline(session_id: str) -> list[dict[str, Any]]:
        if state.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return state.list_timeline_events(session_id)

    @router.get("/sessions/{session_id}/timeline/stream")
    async def stream_timeline_sse(session_id: str, request: Request) -> StreamingResponse:
        if state.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found")

        # Bounded polling cycles so that connections don't live forever; clients
        # using EventSource will auto-reconnect. In tests, set
        # DOCAGENT_SSE_MAX_POLLS to a small value for fast termination.
        max_polls = int(os.environ.get("DOCAGENT_SSE_MAX_POLLS", "1500"))
        poll_interval = float(os.environ.get("DOCAGENT_SSE_POLL_INTERVAL", "0.2"))

        async def generate():
            try:
                last_row_id = int(request.headers.get("last-event-id", "0") or "0")
            except ValueError:
                last_row_id = 0
            for _ in range(max_polls):
                if await request.is_disconnected():
                    return
                new_rows = await asyncio.to_thread(
                    state.list_timeline_events_after, session_id, last_row_id
                )
                for row_id, event in new_rows:
                    yield f"id: {row_id}\n"
                    yield f"data: {_json.dumps(event)}\n\n"
                    last_row_id = row_id
                await asyncio.sleep(poll_interval)

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return router


def _message_with_attachments(request: SendMessageRequest) -> str:
    if not request.attachments:
        return request.message
    references = [
        f"- {attachment.name}: {attachment.markdown_path}"
        for attachment in request.attachments
    ]
    return "\n".join([
        request.message.rstrip(),
        "",
        "Attached workspace inputs:",
        *references,
    ]).strip()
