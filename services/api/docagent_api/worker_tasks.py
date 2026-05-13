from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from docagent_api.celery_app import celery_app
from docagent_api.prompts import build_prompt_bundle
from docagent_api.routes._shared import append_runtime_result, runtime_event_sink, set_session_state
from docagent_api.session_state import RUNNING_STATES
from docagent_contracts import RuntimeSessionState


def _runtime_state_or_default(value: str | None, default: RuntimeSessionState) -> RuntimeSessionState:
    try:
        return RuntimeSessionState(value)
    except ValueError:
        return default


def _get_state():
    from docagent_api.state import DocAgentState
    root = Path(os.environ.get("DOCAGENT_STATE_ROOT", ".local/docagent"))
    return DocAgentState(root, database_url=os.environ.get("DATABASE_URL"))


def _get_adapter():
    from docagent_api.runtime_factory import create_runtime_adapter
    return create_runtime_adapter()


def _ensure_runtime_session(state: Any, adapter: Any, session: dict[str, Any]) -> None:
    runtime_session_id = session.get("runtime_session_id")
    bind_runtime_session = getattr(adapter, "bind_runtime_session", None)
    if runtime_session_id and callable(bind_runtime_session):
        bind_runtime_session(
            session["id"],
            runtime_session_id,
            _runtime_state_or_default(session.get("status"), RuntimeSessionState.IDLE),
        )
        return

    try:
        adapter.get_state(session["id"])
        return
    except Exception:
        pass

    repo_root = Path(os.environ.get("DOCAGENT_REPO_ROOT", "."))
    task = state.get_task(session["task_id"])
    if task is None:
        raise RuntimeError(f"Task not found for session {session['id']}")
    prompt_bundle = build_prompt_bundle(
        repo_root,
        Path(task["workspace_root"]),
        task["id"],
        session["id"],
        task["doc_type_id"],
    )
    result = adapter.create_session(session["id"], prompt_bundle)
    for raw_event in result.raw_events:
        runtime_session_id = raw_event.runtime_session_id
        if runtime_session_id:
            session["runtime"] = raw_event.runtime.value
            session["runtime_session_id"] = runtime_session_id
            break
    append_runtime_result(state, task["id"], session["id"], result)


def _is_cancelled(state: Any, session_id: str) -> bool:
    latest = state.get_session(session_id)
    return latest is not None and latest.get("status") == RuntimeSessionState.CANCELLED.value


@celery_app.task(bind=True, max_retries=0)
def run_session(
    self,
    session_id: str,
    operation_name: str,
    operation_kwargs: dict[str, Any],
    previous_state_on_failure: str | None = None,
) -> None:
    """Execute a runtime operation for a session in the background worker."""
    state = _get_state()
    adapter = _get_adapter()
    session = state.get_session(session_id)
    if session is None:
        return

    try:
        _ensure_runtime_session(state, adapter, session)
        task_id = session["task_id"]
        method = getattr(adapter, operation_name)
        if operation_name.endswith("_stream"):
            result = method(session_id, **operation_kwargs, sink=runtime_event_sink(state, task_id, session_id))
        else:
            result = method(session_id, **operation_kwargs)
        if _is_cancelled(state, session_id):
            state.release_operation_lease(session_id)
            return
        append_runtime_result(state, task_id, session_id, result)
        if _is_cancelled(state, session_id):
            state.release_operation_lease(session_id)
            return
        set_session_state(state, session, result.next_state, task_id=task_id)
        state.release_operation_lease(session_id)
    except Exception as exc:
        from docagent_api.routes._shared import manual_event
        from docagent_contracts import SemanticEventKind, TimelineActor, TimelineStatus
        from uuid import uuid4

        task_id = session["task_id"]
        failure = manual_event(
            task_id, session_id, f"runtime-failed-{uuid4().hex[:8]}",
            TimelineActor.SYSTEM, SemanticEventKind.ERROR,
            f"Runtime operation failed: {exc}", [],
            status=TimelineStatus.FAILED,
        )
        state.append_timeline_event(session_id, asdict(failure))
        # Use the state captured before the transition. If it is missing and the
        # current state is still running, fail closed instead of preserving a stale
        # running_* state forever.
        fallback = RuntimeSessionState.FAILED.value if session["status"] in RUNNING_STATES else session["status"]
        rollback = _runtime_state_or_default(previous_state_on_failure or fallback, RuntimeSessionState.FAILED)
        set_session_state(state, session, rollback, task_id=task_id)
        state.release_operation_lease(session_id)
