from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from dataclasses import asdict
from typing import Any
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from docagent_api.background import BackgroundRuntimeRunner
from docagent_api.response_models import HealthResponse
from docagent_api.routes.doctypes import create_doctypes_router
from docagent_api.routes.sessions import create_sessions_router
from docagent_api.routes.skill_packs import create_skill_packs_router
from docagent_api.routes.tasks import create_tasks_router
from docagent_api.runtime_factory import create_runtime_adapter
from docagent_api.skill_packs import bootstrap_seed_skill_packs
from docagent_api.state import DocAgentState
from docagent_api.routes._shared import manual_event
from docagent_contracts import RuntimeSessionState, SemanticEventKind, TimelineActor, TimelineStatus


def create_app(
    state_root: Path | None = None,
    repo_root: Path | None = None,
    runtime_name: str | None = None,
    runtime_adapter: Any | None = None,
) -> FastAPI:
    runner = BackgroundRuntimeRunner()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        runner.shutdown()

    app = FastAPI(title="DocAgent Workbench API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:5174",
            "http://localhost:5174",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    root = repo_root or Path(os.environ.get("DOCAGENT_REPO_ROOT", "."))
    state = DocAgentState(
        state_root or state_root_from_env() or root / ".local" / "docagent",
        database_url=os.environ.get("DATABASE_URL"),
    )
    bootstrap_seed_skill_packs(state, root / "doc-types")
    _recover_interrupted_sessions(state)
    adapter = runtime_adapter or create_runtime_adapter(runtime_name)

    @app.get("/health", response_model=HealthResponse)
    def health() -> dict[str, str]:
        return {"status": "ok", "runtime": runtime_name or os.environ.get("DOCAGENT_RUNTIME", "mock-acp")}

    app.include_router(create_doctypes_router(root))
    app.include_router(create_skill_packs_router(state, adapter))
    app.include_router(create_tasks_router(state, adapter, root))
    app.include_router(create_sessions_router(state, adapter, runner))

    return app


def _recover_interrupted_sessions(state: DocAgentState) -> None:
    """Fail sessions left in running states after an API/worker interruption."""
    import logging
    running_states = {
        RuntimeSessionState.RUNNING_CONTEXT.value,
        RuntimeSessionState.RUNNING_DRAFT.value,
        RuntimeSessionState.RUNNING_REVISION.value,
        RuntimeSessionState.RUNNING_CHAT.value,
        RuntimeSessionState.RUNNING_CHECKLIST.value,
        RuntimeSessionState.RUNNING_EXPORT.value,
    }
    logger = logging.getLogger(__name__)
    interrupted = state.mark_stale_operations(running_states, RuntimeSessionState.FAILED.value)
    if interrupted:
        for session in interrupted:
            failure = manual_event(
                session["task_id"],
                session["id"],
                f"runtime-interrupted-{uuid4().hex[:8]}",
                TimelineActor.SYSTEM,
                SemanticEventKind.ERROR,
                "Runtime operation interrupted during API startup recovery",
                [],
                status=TimelineStatus.FAILED,
            )
            state.append_timeline_event(session["id"], asdict(failure))
        ids = ", ".join(s["id"] for s in interrupted)
        logger.warning("Marked interrupted running sessions failed during startup recovery: %s", ids)


def state_root_from_env() -> Path | None:
    value = os.environ.get("DOCAGENT_STATE_ROOT")
    return Path(value) if value else None
