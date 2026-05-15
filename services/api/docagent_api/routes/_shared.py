from __future__ import annotations

import os as _os
from dataclasses import asdict
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

from docagent_api.background import BackgroundRuntimeRunner
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
from docagent_api.session_state import InvalidSessionTransition, require_transition
from docagent_api.state import DocAgentState
from docagent_api.time import utc_now


def require_task(state: DocAgentState, task_id: str) -> dict[str, Any]:
    task = state.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def require_session(state: DocAgentState, session_id: str) -> dict[str, Any]:
    session = state.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def prepare_transition(
    state: DocAgentState,
    session: dict[str, Any],
    next_state: RuntimeSessionState,
    task_id: str | None = None,
) -> None:
    try:
        require_transition(session["status"], next_state)
    except InvalidSessionTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    set_session_state(state, session, next_state, task_id=task_id)


def set_session_state(
    state: DocAgentState,
    session: dict[str, Any],
    next_state: RuntimeSessionState,
    task_id: str | None = None,
) -> None:
    session["status"] = next_state.value
    session["updated_at"] = utc_now()
    state.save_session(session)
    if task_id is not None:
        append_acp_status_event(state, session["id"], next_state)
        event = manual_event(
            task_id,
            session["id"],
            f"status-{uuid4().hex[:8]}",
            TimelineActor.SYSTEM,
            SemanticEventKind.SESSION_STATUS,
            f"Session status changed to {next_state.value}",
            [],
            status=TimelineStatus.SUCCEEDED,
        )
        state.append_timeline_event(session["id"], asdict(event))
        append_acp_projection_event(state, session["id"], event)


def append_events(state: DocAgentState, session_id: str, events: list[SemanticTimelineEvent]) -> None:
    for event in events:
        state.append_timeline_event(session_id, asdict(event))
        append_acp_projection_event(state, session_id, event)


def append_runtime_result(
    state: DocAgentState,
    task_id: str,
    session_id: str,
    result: RuntimeOperationResult,
) -> None:
    for update in result.acp_updates:
        state.append_acp_event(
            session_id,
            {**update.payload, "event_type": update.event_type},
            projection=update.projection,
        )
    append_events(state, session_id, result.events)
    for raw_event in result.raw_events:
        if raw_event.runtime_session_id:
            state.bind_runtime_session(session_id, raw_event.runtime.value, raw_event.runtime_session_id)
        state.append_raw_runtime_event(session_id, raw_event)
        if raw_event.runtime is RuntimeKind.OPENHANDS:
            semantic = map_openhands_raw_event(raw_event, task_id)
            if semantic is not None:
                state.append_timeline_event(session_id, asdict(semantic))
                append_acp_projection_event(state, session_id, semantic)


def runtime_event_sink(state: DocAgentState, task_id: str, session_id: str) -> Any:
    def sink(raw_event: Any) -> None:
        state.append_raw_runtime_event(session_id, raw_event)
        if raw_event.runtime is RuntimeKind.OPENHANDS:
            semantic = map_openhands_raw_event(raw_event, task_id)
            if semantic is not None:
                state.append_timeline_event(session_id, asdict(semantic))
                append_acp_projection_event(state, session_id, semantic)
    return sink


def stream_or_sync(adapter: Any, stream_name: str, sync_operation: Any, stream_operation: Any) -> Any:
    stream_method = getattr(adapter, stream_name, None)
    if callable(stream_method):
        return stream_operation(stream_method)
    return sync_operation


def run_runtime_operation(
    state: DocAgentState,
    session: dict[str, Any],
    running_state: RuntimeSessionState,
    operation: Any,
    task_id: str | None = None,
) -> RuntimeOperationResult:
    previous_state = RuntimeSessionState(session["status"])
    prepare_transition(state, session, running_state, task_id=task_id)
    try:
        return operation()
    except HTTPException:
        raise
    except Exception as exc:
        append_acp_error_event(state, session["id"], f"Runtime operation failed: {exc}")
        set_session_state(state, session, previous_state, task_id=task_id)
        raise HTTPException(status_code=502, detail=f"Runtime operation failed: {exc}") from exc


def start_background_runtime_operation(
    state: DocAgentState,
    task_id: str,
    session: dict[str, Any],
    running_state: RuntimeSessionState,
    operation: Any,
    runner: BackgroundRuntimeRunner,
    previous_state_on_failure: RuntimeSessionState | None = None,
    transition_prepared: bool = False,
    operation_name: str | None = None,
    operation_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    session_id = session["id"]
    if runner.is_running(session_id):
        raise HTTPException(
            status_code=409,
            detail=f"A background operation is already running for session {session_id}",
        )
    previous_state = previous_state_on_failure or RuntimeSessionState(session["status"])
    use_celery = _os.environ.get("DOCAGENT_QUEUE", "inline") == "celery"
    lease_id: str | None = None
    if use_celery and operation_name is not None:
        lease_id = f"celery-{uuid4().hex[:12]}"
        if not state.acquire_operation_lease(session_id, lease_id):
            raise HTTPException(
                status_code=409,
                detail=f"A background operation is already running for session {session_id}",
            )

    if not transition_prepared:
        try:
            prepare_transition(state, session, running_state, task_id=task_id)
        except Exception:
            if lease_id:
                state.release_operation_lease(session_id, lease_id)
            raise

    if use_celery and operation_name is not None:
        from docagent_api.worker_tasks import run_session
        try:
            delayed = run_session.delay(
                session["id"],
                operation_name,
                operation_kwargs or {},
                previous_state.value,
            )
        except Exception:
            state.release_operation_lease(session_id, lease_id)
            raise
        task_id_value = getattr(delayed, "id", None)
        if task_id_value:
            state.release_operation_lease(session_id, lease_id)
            state.acquire_operation_lease(session_id, str(task_id_value))
    else:
        def worker() -> None:
            try:
                result = operation()
            except Exception as exc:
                append_acp_error_event(state, session["id"], f"Runtime operation failed: {exc}")
                failure = manual_event(
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
                append_acp_projection_event(state, session["id"], failure)
                set_session_state(state, session, previous_state, task_id=task_id)
                return
            append_runtime_result(state, task_id, session["id"], result)
            set_session_state(state, session, result.next_state, task_id=task_id)

        runner.submit(session["id"], worker)

    return {"session_id": session["id"], "accepted": True, "status": running_state.value}


def runtime_result_response(result: RuntimeOperationResult) -> dict[str, Any]:
    return {
        "session_id": result.session_id,
        "next_state": result.next_state.value,
        "event_count": len(result.events),
        "raw_event_count": len(result.raw_events),
    }


def manual_event(
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


def append_acp_prompt_event(
    state: DocAgentState,
    session_id: str,
    prompt: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    state.append_acp_event(
        session_id,
        {
            "method": "docagent/prompt",
            "prompt": prompt,
            "metadata": metadata or {},
        },
    )


def append_acp_projection_event(
    state: DocAgentState,
    session_id: str,
    event: SemanticTimelineEvent,
) -> None:
    state.append_acp_event(
        session_id,
        {
            "method": "docagent/projection",
            "timeline_event_id": event.id,
        },
        projection={
            "timeline_id": event.id,
            "timeline_kind": event.kind.value,
            "actor": event.actor.value,
            "summary": event.summary,
            "paths": event.paths,
            "status": event.status.value,
        },
    )


def append_acp_status_event(
    state: DocAgentState,
    session_id: str,
    status: RuntimeSessionState,
    summary: str | None = None,
) -> None:
    state.append_acp_event(
        session_id,
        {
            "method": f"session/{status.value}",
            "status": status.value,
            "message": summary or f"Session status changed to {status.value}",
        },
    )


def append_acp_error_event(
    state: DocAgentState,
    session_id: str,
    message: str,
) -> None:
    state.append_acp_event(
        session_id,
        {
            "method": "runtime/error",
            "message": message,
        },
    )
