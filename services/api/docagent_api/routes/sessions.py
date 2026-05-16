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
from fastapi import WebSocket

from docagent_api.background import BackgroundRuntimeRunner
from docagent_api.celery_app import celery_app
from docagent_api.request_models import (
    ApproveOutlineRequest,
    PermissionAnswerRequest,
    PromptRequest,
    ReviseSelectionRequest,
    SendMessageRequest,
)
from docagent_api.response_models import AcpEventResponse, LoopActionResponse, SessionResponse, TimelineEventResponse
from docagent_api.routes._shared import (
    append_runtime_result,
    append_acp_prompt_event,
    append_acp_projection_event,
    manual_event,
    prepare_transition,
    require_session,
    require_task,
    run_runtime_operation,
    runtime_result_response,
    set_session_state,
    start_background_runtime_operation,
)
from docagent_api.routes.acp_ws import handle_acp_websocket
from docagent_api.state import DocAgentState
from docagent_contracts import RuntimeSessionState, SemanticEventKind, TimelineActor

logger = logging.getLogger(__name__)

START_LOOP_PROMPT = "Build context files and propose an outline. Stop when outline approval is required."
APPROVE_OUTLINE_PROMPT = "The outline is approved. Generate the draft in Markdown."
RUN_CHECKLIST_PROMPT = "Run the document type checklist and write reviews/checklist_result.md."
EXPORT_MARKDOWN_PROMPT = "Export the current draft to artifacts/prd-draft.md."


def create_sessions_router(state: DocAgentState, adapter: Any, runner: BackgroundRuntimeRunner) -> APIRouter:
    router = APIRouter()

    def _send_prompt_operation(
        session_id: str,
        prompt: str,
        metadata: dict[str, object],
    ) -> Any:
        send_prompt_method = getattr(adapter, "send_prompt", None)
        if not callable(send_prompt_method):
            raise RuntimeError("Runtime adapter must implement send_prompt")
        return lambda: send_prompt_method(session_id, prompt, metadata)

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
        append_acp_prompt_event(
            state,
            session_id,
            START_LOOP_PROMPT,
            {"action": "start_loop"},
        )
        if background:
            try:
                operation = _send_prompt_operation(
                    session_id,
                    START_LOOP_PROMPT,
                    {"action": "start_loop"},
                )
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail=f"Runtime operation failed: {exc}") from exc
            response.status_code = 202
            return start_background_runtime_operation(
                state,
                task["id"],
                session,
                RuntimeSessionState.RUNNING_CONTEXT,
                operation,
                runner,
                operation_name="send_prompt",
                operation_kwargs={
                    "prompt": START_LOOP_PROMPT,
                    "metadata": {"action": "start_loop"},
                },
            )
        try:
            operation = _send_prompt_operation(
                session_id,
                START_LOOP_PROMPT,
                {"action": "start_loop"},
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=f"Runtime operation failed: {exc}") from exc
        result = run_runtime_operation(
            state, session, RuntimeSessionState.RUNNING_CONTEXT, operation,
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
        append_acp_prompt_event(
            state,
            session_id,
            APPROVE_OUTLINE_PROMPT,
            {
                "action": "approve_outline",
                "outline_markdown": outline_text,
            },
        )
        if not outline_text.endswith("\n"):
            outline_text = f"{outline_text}\n"
        outline_path = Path(task["workspace_root"]) / "draft" / "outline.md"
        outline_path.parent.mkdir(parents=True, exist_ok=True)
        outline_path.write_text(outline_text, encoding="utf-8")
        if background:
            try:
                operation = _send_prompt_operation(
                    session_id,
                    APPROVE_OUTLINE_PROMPT,
                    {
                        "action": "approve_outline",
                        "outline_markdown": outline_text,
                    },
                )
            except RuntimeError as exc:
                set_session_state(state, session, RuntimeSessionState.AWAIT_OUTLINE_APPROVAL, task_id=task["id"])
                raise HTTPException(status_code=502, detail=f"Runtime operation failed: {exc}") from exc
            response.status_code = 202
            return start_background_runtime_operation(
                state, task["id"], session, RuntimeSessionState.RUNNING_DRAFT, operation,
                runner,
                previous_state_on_failure=RuntimeSessionState.AWAIT_OUTLINE_APPROVAL,
                transition_prepared=True,
                operation_name="send_prompt",
                operation_kwargs={
                    "prompt": APPROVE_OUTLINE_PROMPT,
                    "metadata": {
                        "action": "approve_outline",
                        "outline_markdown": outline_text,
                    },
                },
            )
        try:
            operation = _send_prompt_operation(
                session_id,
                APPROVE_OUTLINE_PROMPT,
                {
                    "action": "approve_outline",
                    "outline_markdown": outline_text,
                },
            )
            result = operation()
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
        revision_prompt = (
            "Revise this selected text according to the instruction.\n\n"
            f"Selection:\n{request.selected_text}\n\nInstruction:\n{request.instruction}"
        )
        append_acp_prompt_event(
            state,
            session_id,
            revision_prompt,
            {
                "action": "revise_selection",
                "selection": request.selected_text,
                "instruction": request.instruction,
            },
        )
        try:
            prepare_transition(state, session, RuntimeSessionState.RUNNING_REVISION, task_id=task["id"])
            if background:
                operation = _send_prompt_operation(
                    session_id,
                    revision_prompt,
                    {
                        "action": "revise_selection",
                        "selection": request.selected_text,
                        "instruction": request.instruction,
                    },
                )
                response.status_code = 202
                return start_background_runtime_operation(
                    state, task["id"], session, RuntimeSessionState.RUNNING_REVISION, operation,
                    runner,
                    previous_state_on_failure=previous_state, transition_prepared=True,
                    operation_name="send_prompt",
                    operation_kwargs={
                        "prompt": revision_prompt,
                        "metadata": {
                            "action": "revise_selection",
                            "selection": request.selected_text,
                            "instruction": request.instruction,
                        },
                    },
                )
            operation = _send_prompt_operation(
                session_id,
                revision_prompt,
                {
                    "action": "revise_selection",
                    "selection": request.selected_text,
                    "instruction": request.instruction,
                },
            )
            result = operation()
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
        append_acp_prompt_event(
            state,
            session_id,
            RUN_CHECKLIST_PROMPT,
            {"action": "run_checklist"},
        )
        if background:
            try:
                operation = _send_prompt_operation(
                    session_id,
                    RUN_CHECKLIST_PROMPT,
                    {"action": "run_checklist"},
                )
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail=f"Runtime operation failed: {exc}") from exc
            response.status_code = 202
            return start_background_runtime_operation(
                state,
                task["id"],
                session,
                RuntimeSessionState.RUNNING_CHECKLIST,
                operation,
                runner,
                operation_name="send_prompt",
                operation_kwargs={
                    "prompt": RUN_CHECKLIST_PROMPT,
                    "metadata": {"action": "run_checklist"},
                },
            )
        try:
            operation = _send_prompt_operation(
                session_id,
                RUN_CHECKLIST_PROMPT,
                {"action": "run_checklist"},
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=f"Runtime operation failed: {exc}") from exc
        result = run_runtime_operation(
            state, session, RuntimeSessionState.RUNNING_CHECKLIST, operation,
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
        append_acp_prompt_event(
            state,
            session_id,
            EXPORT_MARKDOWN_PROMPT,
            {"action": "export_markdown"},
        )
        if background:
            try:
                operation = _send_prompt_operation(
                    session_id,
                    EXPORT_MARKDOWN_PROMPT,
                    {"action": "export_markdown"},
                )
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail=f"Runtime operation failed: {exc}") from exc
            response.status_code = 202
            return start_background_runtime_operation(
                state,
                task["id"],
                session,
                RuntimeSessionState.RUNNING_EXPORT,
                operation,
                runner,
                operation_name="send_prompt",
                operation_kwargs={
                    "prompt": EXPORT_MARKDOWN_PROMPT,
                    "metadata": {"action": "export_markdown"},
                },
            )
        try:
            operation = _send_prompt_operation(
                session_id,
                EXPORT_MARKDOWN_PROMPT,
                {"action": "export_markdown"},
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=f"Runtime operation failed: {exc}") from exc
        result = run_runtime_operation(
            state, session, RuntimeSessionState.RUNNING_EXPORT, operation,
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
        return _send_prompt(
            session_id,
            request,
            response,
            background=background,
            action="send_message",
        )

    @router.post("/sessions/{session_id}/prompt", response_model=LoopActionResponse)
    def send_prompt(
        session_id: str,
        request: PromptRequest,
        response: Response,
        background: bool = Query(default=False),
    ) -> dict[str, Any]:
        return _send_prompt(
            session_id,
            SendMessageRequest(message=request.prompt),
            response,
            background=background,
            action=str(request.metadata.get("action") or "send_message"),
            metadata=request.metadata,
        )

    def _send_prompt(
        session_id: str,
        request: SendMessageRequest,
        response: Response,
        *,
        background: bool,
        action: str,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        session = require_session(state, session_id)
        task = require_task(state, session["task_id"])
        runtime_message = _message_with_attachments(request)
        prompt_metadata = {
            "action": action,
            **(metadata or {}),
        }
        append_acp_prompt_event(state, session_id, runtime_message, prompt_metadata)
        if background:
            send_prompt_method = getattr(adapter, "send_prompt", None)
            if not callable(send_prompt_method):
                raise HTTPException(
                    status_code=502,
                    detail="Runtime operation failed: Runtime adapter must implement send_prompt",
                )
            user_event = manual_event(
                task["id"], session_id, f"user-{uuid4().hex[:8]}",
                TimelineActor.USER, SemanticEventKind.USER_MESSAGE, runtime_message, [],
            )
            state.append_timeline_event(session_id, asdict(user_event))
            append_acp_projection_event(state, session_id, user_event)
            operation = lambda: send_prompt_method(session_id, runtime_message, prompt_metadata)
            response.status_code = 202
            return start_background_runtime_operation(
                state,
                task["id"],
                session,
                RuntimeSessionState.RUNNING_CHAT,
                operation,
                runner,
                operation_name="send_prompt",
                operation_kwargs={
                    "prompt": runtime_message,
                    "metadata": prompt_metadata,
                },
            )
        try:
            operation = _send_prompt_operation(session_id, runtime_message, prompt_metadata)
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=f"Runtime operation failed: {exc}") from exc
        result = run_runtime_operation(
            state, session, RuntimeSessionState.RUNNING_CHAT,
            operation,
            task_id=task["id"],
        )
        append_runtime_result(state, task["id"], session_id, result)
        if not result.events:
            user_event = manual_event(
                task["id"], session_id, f"user-{uuid4().hex[:8]}",
                TimelineActor.USER, SemanticEventKind.USER_MESSAGE, runtime_message, [],
            )
            state.append_timeline_event(session_id, asdict(user_event))
            append_acp_projection_event(state, session_id, user_event)
        set_session_state(state, session, result.next_state, task_id=task["id"])
        return runtime_result_response(result)

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

    @router.post("/sessions/{session_id}/permissions/{request_id}/answer", response_model=LoopActionResponse)
    def answer_permission(
        session_id: str,
        request_id: str,
        request: PermissionAnswerRequest,
    ) -> dict[str, Any]:
        session = require_session(state, session_id)
        task = require_task(state, session["task_id"])
        answer_method = getattr(adapter, "answer_permission", None)
        if not callable(answer_method):
            raise HTTPException(status_code=501, detail="Runtime adapter does not support permission responses.")
        try:
            result = answer_method(session_id, request_id, request.decision)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Runtime permission response failed: {exc}") from exc
        # Store the UI decision and runtime confirmation as separate ACP rows; if
        # confirmation persistence fails later, this response row remains as audit.
        state.append_acp_event(
            session_id,
            {
                "event_type": "permission/response",
                "request_id": request_id,
                "decision": request.decision,
            },
        )
        append_runtime_result(state, task["id"], session_id, result)
        set_session_state(state, session, result.next_state, task_id=task["id"])
        return {
            "session_id": session_id,
            "next_state": result.next_state.value,
            "accepted": True,
            "status": result.next_state.value,
        }

    @router.get("/sessions/{session_id}/timeline", response_model=list[TimelineEventResponse])
    def get_timeline(session_id: str) -> list[dict[str, Any]]:
        session = require_session(state, session_id)
        require_task(state, session["task_id"])
        # Compatibility/read-model endpoint only. Authoring UI reads ACP events.
        return state.list_timeline_events(session_id)

    @router.get("/sessions/{session_id}/events", response_model=list[AcpEventResponse])
    def get_acp_events(session_id: str) -> list[dict[str, Any]]:
        session = require_session(state, session_id)
        require_task(state, session["task_id"])
        return state.list_acp_events(session_id)

    @router.get("/sessions/{session_id}/events/stream")
    async def stream_acp_events_sse(session_id: str, request: Request) -> StreamingResponse:
        session = require_session(state, session_id)
        require_task(state, session["task_id"])

        max_polls = int(os.environ.get("DOCAGENT_SSE_MAX_POLLS", "1500"))
        poll_interval = float(os.environ.get("DOCAGENT_SSE_POLL_INTERVAL", "0.2"))

        async def generate():
            try:
                last_sequence = int(request.headers.get("last-event-id", "0") or "0")
            except ValueError:
                last_sequence = 0
            for _ in range(max_polls):
                if await request.is_disconnected():
                    return
                new_events = await asyncio.to_thread(
                    state.list_acp_events_after, session_id, last_sequence
                )
                for event in new_events:
                    sequence = int(event["sequence"])
                    yield f"id: {sequence}\n"
                    yield f"data: {_json.dumps(event)}\n\n"
                    last_sequence = sequence
                await asyncio.sleep(poll_interval)

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @router.websocket("/sessions/{session_id}/acp/ws")
    async def acp_websocket(session_id: str, websocket: WebSocket) -> None:
        await handle_acp_websocket(websocket, session_id, state, adapter)

    @router.get("/sessions/{session_id}/timeline/stream")
    async def stream_timeline_sse(session_id: str, request: Request) -> StreamingResponse:
        session = require_session(state, session_id)
        require_task(state, session["task_id"])

        # Compatibility/read-model stream only. Authoring UI uses /events/stream.
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
