from __future__ import annotations

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
) -> None:
    try:
        require_transition(session["status"], next_state)
    except InvalidSessionTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    set_session_state(state, session, next_state)


def set_session_state(
    state: DocAgentState,
    session: dict[str, Any],
    next_state: RuntimeSessionState,
) -> None:
    session["status"] = next_state.value
    session["updated_at"] = utc_now()
    state.save_session(session)


def append_events(state: DocAgentState, session_id: str, events: list[SemanticTimelineEvent]) -> None:
    for event in events:
        state.append_timeline_event(session_id, asdict(event))


def append_runtime_result(
    state: DocAgentState,
    task_id: str,
    session_id: str,
    result: RuntimeOperationResult,
) -> None:
    append_events(state, session_id, result.events)
    for raw_event in result.raw_events:
        state.append_raw_runtime_event(session_id, raw_event)
        if raw_event.runtime is RuntimeKind.OPENHANDS:
            semantic = map_openhands_raw_event(raw_event, task_id)
            if semantic is not None:
                state.append_timeline_event(session_id, asdict(semantic))


def runtime_event_sink(state: DocAgentState, task_id: str, session_id: str) -> Any:
    def sink(raw_event: Any) -> None:
        state.append_raw_runtime_event(session_id, raw_event)
        if raw_event.runtime is RuntimeKind.OPENHANDS:
            semantic = map_openhands_raw_event(raw_event, task_id)
            if semantic is not None:
                state.append_timeline_event(session_id, asdict(semantic))
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
) -> RuntimeOperationResult:
    previous_state = RuntimeSessionState(session["status"])
    prepare_transition(state, session, running_state)
    try:
        return operation()
    except HTTPException:
        raise
    except Exception as exc:
        set_session_state(state, session, previous_state)
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
) -> dict[str, Any]:
    previous_state = previous_state_on_failure or RuntimeSessionState(session["status"])
    if not transition_prepared:
        prepare_transition(state, session, running_state)

    def worker() -> None:
        try:
            result = operation()
        except Exception as exc:
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
            set_session_state(state, session, previous_state)
            return
        append_runtime_result(state, task_id, session["id"], result)
        set_session_state(state, session, result.next_state)

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
