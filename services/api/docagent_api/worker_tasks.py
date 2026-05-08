from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from docagent_api.celery_app import celery_app
from docagent_api.routes._shared import append_runtime_result, set_session_state
from docagent_contracts import RuntimeSessionState


def _get_state():
    from docagent_api.state import DocAgentState
    root = Path(os.environ.get("DOCAGENT_STATE_ROOT", ".local/docagent"))
    return DocAgentState(root, database_url=os.environ.get("DATABASE_URL"))


def _get_adapter():
    from docagent_api.runtime_factory import create_runtime_adapter
    return create_runtime_adapter()


def _ensure_runtime_session(state: Any, adapter: Any, session: dict[str, Any]) -> None:
    try:
        adapter.get_state(session["id"])
        return
    except Exception:
        pass

    from docagent_api.prompts import build_prompt_bundle

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
    append_runtime_result(state, task["id"], session["id"], result)


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
        method = getattr(adapter, operation_name)
        result = method(session_id, **operation_kwargs)
        task_id = session["task_id"]
        append_runtime_result(state, task_id, session_id, result)
        set_session_state(state, session, result.next_state)
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
        # Use the state captured before the transition (passed from the dispatcher),
        # falling back to the current DB status only if not provided.
        rollback = RuntimeSessionState(previous_state_on_failure or session["status"])
        set_session_state(state, session, rollback)
