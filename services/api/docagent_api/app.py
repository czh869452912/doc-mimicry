from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from docagent_api.background import BackgroundRuntimeRunner
from docagent_api.response_models import HealthResponse
from docagent_api.routes.doctypes import create_doctypes_router
from docagent_api.routes.sessions import create_sessions_router
from docagent_api.routes.tasks import create_tasks_router
from docagent_api.runtime_factory import create_runtime_adapter
from docagent_api.state import DocAgentState
from docagent_contracts import RuntimeSessionState


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
    root = repo_root or Path.cwd()
    state = DocAgentState(
        state_root or state_root_from_env() or root / ".local" / "docagent",
        database_url=os.environ.get("DATABASE_URL"),
    )
    _warn_interrupted_sessions(state)
    adapter = runtime_adapter or create_runtime_adapter(runtime_name)

    @app.get("/health", response_model=HealthResponse)
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(create_doctypes_router(root))
    app.include_router(create_tasks_router(state, adapter, root))
    app.include_router(create_sessions_router(state, adapter, runner))

    return app


def _warn_interrupted_sessions(state: DocAgentState) -> None:
    """Log a warning for sessions left in running states (Celery will recover them)."""
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
    interrupted = [s for s in state.list_sessions() if s["status"] in running_states]
    if interrupted:
        ids = ", ".join(s["id"] for s in interrupted)
        logger.warning("Sessions left in running state (will be recovered by worker): %s", ids)


def state_root_from_env() -> Path | None:
    value = os.environ.get("DOCAGENT_STATE_ROOT")
    return Path(value) if value else None
