# Backend Polish Implementation Plan

> **Archive note (2026-05-17):** This completed plan preserves its original
> execution checklist for historical traceability. Any unchecked boxes below are
> not active work; use active plan/review directories for current tasks.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean up and restructure the Python API backend — delete dead code, consolidate duplicated logic, add a proper chat session state, add Pydantic response models, and split the 680-line `app.py` monolith into focused route modules.

**Architecture:** All changes are within `services/api/`. Route modules use factory functions `create_*_router(state, adapter, root)` so the existing closure pattern is preserved. Shared helpers move to `routes/_shared.py`. Pydantic response models go in `response_models.py`. `RUNNING_CHAT` is added to the contracts package before any app changes.

**Tech Stack:** FastAPI, Pydantic v2, pytest, Python 3.10+

---

## File Map

**Delete:**
- `services/api/docagent_api/models.py` — dead code (TypedDicts never imported by app.py)

**Create:**
- `services/api/docagent_api/response_models.py` — Pydantic response model classes
- `services/api/docagent_api/routes/__init__.py` — empty
- `services/api/docagent_api/routes/_shared.py` — all helpers extracted from app.py
- `services/api/docagent_api/routes/doctypes.py` — GET /doc-types, GET /doc-types/{id}
- `services/api/docagent_api/routes/tasks.py` — task CRUD, workspace, draft, sessions list, text input
- `services/api/docagent_api/routes/sessions.py` — all session operation routes

**Modify:**
- `packages/contracts/docagent_contracts/runtime.py` — add `RUNNING_CHAT` to `RuntimeSessionState`
- `packages/contracts/tests/test_runtime_contracts.py` — test new state
- `services/api/docagent_api/session_state.py` — add `RUNNING_CHAT` to `ALLOWED_TRANSITIONS`
- `services/api/docagent_api/app.py` — reduce to factory + health + router includes; use `RUNNING_CHAT` for `send_message`
- `services/api/tests/test_phase3_api.py` — add test for `send_message` state

---

## Task 1: Delete dead code (I3)

**Files:**
- Delete: `services/api/docagent_api/models.py`

- [ ] **Step 1: Verify models.py is not imported anywhere**

```bash
grep -r "from docagent_api.models" services/api/
grep -r "import models" services/api/
```

Expected: no output (zero matches).

- [ ] **Step 2: Delete the file**

```bash
rm services/api/docagent_api/models.py
```

- [ ] **Step 3: Run tests to confirm nothing broke**

```bash
python -m pytest services/api/tests/ -q
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "Remove unused models.py (I3)"
```

---

## Task 2: Consolidate duplicate normalize_task (M1)

**Files:**
- Modify: `services/api/docagent_api/app.py`

`DocAgentState.get_task()` already calls `_normalized_task()` before returning, so the `_normalize_task(task)` call inside `_require_task` in `app.py` is redundant. Remove it. Keep `_title_from_description` — it is still used by the `create_task` route.

- [ ] **Step 1: Write failing test confirming normalization still works after removal**

Add to `services/api/tests/test_api.py` (or `test_phase2_api.py`):

```python
def test_task_without_explicit_title_gets_title_from_description(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build a search feature"}).json()

    fetched = client.get(f"/tasks/{task['id']}").json()

    assert fetched["title"] == "Build a search feature"
    assert fetched["description"] == "Build a search feature"
```

- [ ] **Step 2: Run to confirm it passes now** (normalization is already working)

```bash
python -m pytest services/api/tests/ -k "test_task_without_explicit_title" -v
```

Expected: PASS.

- [ ] **Step 3: Remove `_normalize_task` and its call from app.py**

In `services/api/docagent_api/app.py`, find `_require_task`:

```python
def _require_task(state: DocAgentState, task_id: str) -> dict[str, Any]:
    task = state.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    _normalize_task(task)   # <-- remove this line
    return task
```

Remove the `_normalize_task(task)` call so it reads:

```python
def _require_task(state: DocAgentState, task_id: str) -> dict[str, Any]:
    task = state.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
```

Then delete the `_normalize_task` function entirely (lines ~496-500):

```python
# DELETE this entire function:
def _normalize_task(task: dict[str, Any]) -> None:
    description = str(task.get("description") or task.get("brief") or "")
    task["description"] = description
    task["brief"] = str(task.get("brief") or description)
    task["title"] = str(task.get("title") or _title_from_description(description))
```

- [ ] **Step 4: Run all tests**

```bash
python -m pytest services/api/tests/ -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add services/api/docagent_api/app.py services/api/tests/
git commit -m "Remove redundant _normalize_task from app.py (M1)"
```

---

## Task 3: Add RUNNING_CHAT session state (I4)

**Files:**
- Modify: `packages/contracts/docagent_contracts/runtime.py`
- Modify: `packages/contracts/tests/test_runtime_contracts.py`
- Modify: `services/api/docagent_api/session_state.py`
- Modify: `services/api/docagent_api/app.py`
- Modify: `services/api/tests/test_phase3_api.py`

`send_message` currently forces `RUNNING_REVISION` even for free-form chat. `RUNNING_REVISION` implies a document rewrite operation. A dedicated `RUNNING_CHAT` state expresses the actual semantics.

- [ ] **Step 1: Write failing test for the new state**

Add to `services/api/tests/test_phase3_api.py`:

```python
def test_send_message_background_uses_running_chat_state(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    client.post(f"/sessions/{session['id']}/loop/start")

    response = client.post(
        f"/sessions/{session['id']}/messages?background=true",
        json={"message": "hello"},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "running_chat"
```

- [ ] **Step 2: Run to confirm it fails**

```bash
python -m pytest services/api/tests/test_phase3_api.py::test_send_message_background_uses_running_chat_state -v
```

Expected: FAIL — `"running_revision" != "running_chat"`.

- [ ] **Step 3: Add RUNNING_CHAT to RuntimeSessionState**

In `packages/contracts/docagent_contracts/runtime.py`, add the new value after `RUNNING_REVISION`:

```python
class RuntimeSessionState(str, Enum):
    IDLE = "idle"
    RUNNING_CONTEXT = "running_context"
    AWAIT_OUTLINE_APPROVAL = "await_outline_approval"
    RUNNING_DRAFT = "running_draft"
    DRAFT_READY = "draft_ready"
    RUNNING_REVISION = "running_revision"
    RUNNING_CHAT = "running_chat"        # NEW
    RUNNING_CHECKLIST = "running_checklist"
    RUNNING_EXPORT = "running_export"
    PAUSED = "paused"
    FAILED = "failed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
```

- [ ] **Step 4: Add test for the new enum value**

Add to `packages/contracts/tests/test_runtime_contracts.py`:

```python
def test_running_chat_state_exists() -> None:
    from docagent_contracts import RuntimeSessionState
    assert RuntimeSessionState.RUNNING_CHAT.value == "running_chat"
```

Run: `python -m pytest packages/contracts/tests/ -q` — should PASS.

- [ ] **Step 5: Add RUNNING_CHAT to ALLOWED_TRANSITIONS**

In `services/api/docagent_api/session_state.py`, add `RUNNING_CHAT` transitions:

```python
ALLOWED_TRANSITIONS: dict[RuntimeSessionState, set[RuntimeSessionState]] = {
    RuntimeSessionState.IDLE: {
        RuntimeSessionState.RUNNING_CONTEXT,
        RuntimeSessionState.RUNNING_REVISION,
        RuntimeSessionState.RUNNING_CHAT,      # NEW
        RuntimeSessionState.CANCELLED,
    },
    # ... existing entries unchanged ...
    RuntimeSessionState.DRAFT_READY: {
        RuntimeSessionState.RUNNING_REVISION,
        RuntimeSessionState.RUNNING_CHAT,      # NEW
        RuntimeSessionState.RUNNING_CHECKLIST,
        RuntimeSessionState.RUNNING_EXPORT,
        RuntimeSessionState.COMPLETED,
        RuntimeSessionState.CANCELLED,
    },
    RuntimeSessionState.RUNNING_CHAT: {        # NEW entry
        RuntimeSessionState.DRAFT_READY,
        RuntimeSessionState.FAILED,
        RuntimeSessionState.CANCELLED,
    },
    RuntimeSessionState.FAILED: {
        RuntimeSessionState.RUNNING_CONTEXT,
        RuntimeSessionState.RUNNING_DRAFT,
        RuntimeSessionState.RUNNING_REVISION,
        RuntimeSessionState.RUNNING_CHAT,      # NEW
        RuntimeSessionState.CANCELLED,
    },
    # ... rest unchanged ...
}
```

- [ ] **Step 6: Add RUNNING_CHAT to _recover_interrupted_sessions in app.py**

In `services/api/docagent_api/app.py`, find `_recover_interrupted_sessions`:

```python
def _recover_interrupted_sessions(state: DocAgentState) -> None:
    running_states = {
        RuntimeSessionState.RUNNING_CONTEXT.value,
        RuntimeSessionState.RUNNING_DRAFT.value,
        RuntimeSessionState.RUNNING_REVISION.value,
        RuntimeSessionState.RUNNING_CHAT.value,      # ADD THIS
        RuntimeSessionState.RUNNING_CHECKLIST.value,
        RuntimeSessionState.RUNNING_EXPORT.value,
    }
```

- [ ] **Step 7: Switch send_message background to use RUNNING_CHAT**

In `app.py`, find the `send_message` route. Change the `_start_background_runtime_operation` call:

```python
# Before:
return _start_background_runtime_operation(
    state,
    task["id"],
    session,
    RuntimeSessionState.RUNNING_REVISION,   # OLD
    operation,
)

# After:
return _start_background_runtime_operation(
    state,
    task["id"],
    session,
    RuntimeSessionState.RUNNING_CHAT,       # NEW
    operation,
)
```

The sync path (non-background) should also change — it uses `_run_runtime_operation` with `RUNNING_REVISION`. Update both occurrences in `send_message`:

```python
# sync path (line ~451):
result = _run_runtime_operation(
    state,
    session,
    RuntimeSessionState.RUNNING_CHAT,       # was RUNNING_REVISION
    lambda: adapter.send_message(session_id, request.message),
)
```

- [ ] **Step 8: Run all tests**

```bash
python -m pytest services/api/tests/ packages/contracts/tests/ -q
```

Expected: all pass including the new test.

- [ ] **Step 9: Commit**

```bash
git add packages/contracts/ services/api/docagent_api/ services/api/tests/
git commit -m "Add RUNNING_CHAT state for send_message operations (I4)"
```

---

## Task 4: Add Pydantic response models (I2)

**Files:**
- Create: `services/api/docagent_api/response_models.py`
- Modify: `services/api/docagent_api/app.py` (add `response_model=` to each route)

- [ ] **Step 1: Create response_models.py**

Create `services/api/docagent_api/response_models.py`:

```python
from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class DocTypeSummaryResponse(BaseModel):
    id: str
    title: str
    has_skill: bool
    resource_groups: dict[str, list[str]]
    skill_markdown: str | None = None


class TaskResponse(BaseModel):
    id: str
    doc_type_id: str
    brief: str
    title: str
    description: str
    workspace_root: str
    created_at: str
    updated_at: str


class SessionResponse(BaseModel):
    id: str
    task_id: str
    status: str
    created_at: str
    updated_at: str


class WorkspaceFileSummary(BaseModel):
    path: str
    group: str
    kind: str


class WorkspaceResponse(BaseModel):
    task_id: str
    root: str
    files: list[WorkspaceFileSummary]


class WorkspaceFileContentResponse(BaseModel):
    path: str
    content: str


class DraftResponse(BaseModel):
    task_id: str
    markdown: str


class ImportedInputResponse(BaseModel):
    id: str
    status: str
    source_path: str
    markdown_path: str
    conversion_report_path: str
    original_filename: str
    created_at: str
    event: dict | None = None


class LoopActionResponse(BaseModel):
    session_id: str
    next_state: str | None = None
    event_count: int | None = None
    raw_event_count: int | None = None
    paths: list[str] | None = None
    artifact_path: str | None = None
    accepted: bool | None = None
    status: str | None = None


class TimelineEventResponse(BaseModel):
    id: str
    session_id: str
    task_id: str
    actor: str
    kind: str
    raw_event_id: str | None
    summary: str
    paths: list[str]
    status: str
    created_at: str
```

- [ ] **Step 2: Write a test confirming OpenAPI schema now includes response fields**

Add to `services/api/tests/test_api.py`:

```python
def test_openapi_schema_includes_task_response_fields(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    schema = client.get("/openapi.json").json()

    task_schema = schema["components"]["schemas"]["TaskResponse"]
    assert "title" in task_schema["properties"]
    assert "doc_type_id" in task_schema["properties"]
```

Run: `python -m pytest services/api/tests/test_api.py::test_openapi_schema_includes_task_response_fields -v`

Expected: FAIL (schema key doesn't exist yet).

- [ ] **Step 3: Add response_model= to each route in app.py**

At the top of `app.py`, import the response models:

```python
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
```

Then annotate each route. Representative examples (apply the same pattern to every route):

```python
@app.get("/health", response_model=HealthResponse)
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/doc-types", response_model=list[DocTypeSummaryResponse])
def doc_types() -> list[dict[str, Any]]:
    return list_doc_types(root / "doc-types")

@app.post("/tasks", response_model=TaskResponse)
def create_task(request: CreateTaskRequest) -> dict[str, Any]:
    ...

@app.get("/tasks", response_model=list[TaskResponse])
def list_tasks() -> list[dict[str, Any]]:
    ...

@app.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: str) -> dict[str, Any]:
    ...

@app.get("/tasks/{task_id}/workspace", response_model=WorkspaceResponse)
def get_workspace(task_id: str) -> dict[str, Any]:
    ...

@app.get("/tasks/{task_id}/workspace/files", response_model=WorkspaceFileContentResponse)
def get_workspace_file(task_id: str, file_path: str = Query(alias="path")) -> dict[str, str]:
    ...

@app.get("/tasks/{task_id}/draft", response_model=DraftResponse)
def get_draft(task_id: str) -> dict[str, str]:
    ...

@app.put("/tasks/{task_id}/draft", response_model=DraftResponse)
def update_draft(task_id: str, request: UpdateDraftRequest) -> dict[str, str]:
    ...

@app.post("/tasks/{task_id}/sessions", response_model=SessionResponse)
def create_session(task_id: str) -> dict[str, Any]:
    ...

@app.get("/tasks/{task_id}/sessions", response_model=list[SessionResponse])
def list_task_sessions(task_id: str) -> list[dict[str, Any]]:
    ...

@app.post("/tasks/{task_id}/inputs/text", response_model=ImportedInputResponse)
def add_text_input(task_id: str, request: ImportTextRequest) -> dict[str, Any]:
    ...

@app.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: str) -> dict[str, Any]:
    ...

@app.post("/sessions/{session_id}/loop/start", response_model=LoopActionResponse)
def start_loop(...) -> dict[str, Any]:
    ...

@app.post("/sessions/{session_id}/outline/approve", response_model=LoopActionResponse)
def approve_outline(...) -> dict[str, Any]:
    ...

@app.post("/sessions/{session_id}/revision/selection", response_model=LoopActionResponse)
def revise_selection(...) -> dict[str, Any]:
    ...

@app.post("/sessions/{session_id}/checklist/run", response_model=LoopActionResponse)
def run_checklist(...) -> dict[str, Any]:
    ...

@app.post("/sessions/{session_id}/artifacts/export-markdown", response_model=LoopActionResponse)
def export_markdown(...) -> dict[str, Any]:
    ...

@app.post("/sessions/{session_id}/messages", response_model=LoopActionResponse)
def send_message(...) -> dict[str, Any]:
    ...

@app.post("/sessions/{session_id}/cancel", response_model=LoopActionResponse)
def cancel_session(session_id: str) -> dict[str, Any]:
    ...

@app.get("/sessions/{session_id}/timeline", response_model=list[TimelineEventResponse])
def get_timeline(session_id: str) -> list[dict[str, Any]]:
    ...
```

- [ ] **Step 4: Run all tests**

```bash
python -m pytest services/api/tests/ -q
```

Expected: all pass, including the new OpenAPI schema test.

- [ ] **Step 5: Commit**

```bash
git add services/api/docagent_api/response_models.py services/api/docagent_api/app.py services/api/tests/
git commit -m "Add Pydantic response models and OpenAPI annotations (I2)"
```

---

## Task 5: Split app.py into route modules (I1)

**Files:**
- Create: `services/api/docagent_api/routes/__init__.py`
- Create: `services/api/docagent_api/routes/_shared.py`
- Create: `services/api/docagent_api/routes/doctypes.py`
- Create: `services/api/docagent_api/routes/tasks.py`
- Create: `services/api/docagent_api/routes/sessions.py`
- Modify: `services/api/docagent_api/app.py`

The pattern: each module exports a `create_*_router(...)` factory that closes over `state`, `adapter`, and/or `root`. Helpers are shared via `routes/_shared.py`.

- [ ] **Step 1: Write a smoke test confirming all route prefixes still work after refactor**

Add to `services/api/tests/test_api.py`:

```python
def test_all_route_prefixes_respond_after_refactor(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    assert client.get("/health").status_code == 200
    assert client.get("/doc-types").status_code == 200
    assert client.get("/tasks").status_code == 200
```

Run: `python -m pytest services/api/tests/test_api.py::test_all_route_prefixes_respond_after_refactor -v`

Expected: PASS (this baseline test passes before we start moving code, and will catch any breakage during the split).

- [ ] **Step 2: Create routes/__init__.py**

```bash
mkdir -p services/api/docagent_api/routes
touch services/api/docagent_api/routes/__init__.py
```

File contents: empty.

- [ ] **Step 3: Create routes/_shared.py**

Move all private helper functions from `app.py` to this file. Each helper currently takes `state` and/or `adapter` as parameters — no change to signatures needed:

```python
# services/api/docagent_api/routes/_shared.py
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from threading import Thread
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

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

    Thread(target=worker, daemon=True).start()
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
```

- [ ] **Step 4: Create routes/doctypes.py**

```python
# services/api/docagent_api/routes/doctypes.py
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from docagent_api.doctypes import get_doc_type, list_doc_types
from docagent_api.response_models import DocTypeSummaryResponse


def create_doctypes_router(root: Path) -> APIRouter:
    router = APIRouter()

    @router.get("/doc-types", response_model=list[DocTypeSummaryResponse])
    def doc_types() -> list[dict[str, Any]]:
        return list_doc_types(root / "doc-types")

    @router.get("/doc-types/{doc_type_id}", response_model=DocTypeSummaryResponse)
    def doc_type_detail(doc_type_id: str) -> dict[str, Any]:
        detail = get_doc_type(root / "doc-types", doc_type_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Document type not found")
        return detail

    return router
```

- [ ] **Step 5: Create routes/tasks.py**

```python
# services/api/docagent_api/routes/tasks.py
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from docagent_api.doctypes import get_doc_type
from docagent_api.drafts import read_draft, write_draft
from docagent_api.imports import import_text_input
from docagent_api.prompts import build_prompt_bundle
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
    require_session,
    require_task,
    set_session_state,
)
from docagent_api.state import DocAgentState
from docagent_api.time import utc_now
from docagent_api.workspace_files import list_workspace_files, read_workspace_text_file
from docagent_contracts import SemanticEventKind, TimelineActor
from docagent_workspace import create_workspace


class CreateTaskRequest:
    pass  # defined in app.py; import from there or re-define here


def create_tasks_router(state: DocAgentState, adapter: Any, root: Path) -> APIRouter:
    router = APIRouter()

    @router.get("/tasks", response_model=list[TaskResponse])
    def list_tasks() -> list[dict[str, Any]]:
        return state.list_tasks()

    @router.post("/tasks", response_model=TaskResponse)
    def create_task(request: Any) -> dict[str, Any]:
        # request type: CreateTaskRequest (imported from app.py or re-declared here)
        ...

    # ... all other task routes ...

    return router
```

**Important:** Rather than re-declaring Pydantic request models in each routes file, move all request model classes (`CreateTaskRequest`, `SendMessageRequest`, etc.) to a new `services/api/docagent_api/request_models.py` file and import from there in both `app.py` and the routes files.

Create `services/api/docagent_api/request_models.py`:

```python
# services/api/docagent_api/request_models.py
from __future__ import annotations
from pydantic import BaseModel


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
```

Then update `app.py` to import from `request_models` instead of defining inline.

Full `routes/tasks.py`:

```python
# services/api/docagent_api/routes/tasks.py
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from docagent_api.doctypes import get_doc_type
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
    set_session_state,
)
from docagent_api.state import DocAgentState
from docagent_api.time import utc_now
from docagent_api.workspace_files import list_workspace_files, read_workspace_text_file
from docagent_contracts import SemanticEventKind, TimelineActor
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
        prompt_bundle = build_prompt_bundle(
            root,
            Path(task["workspace_root"]),
            task["id"],
            session_id,
            task["doc_type_id"],
        )
        result = adapter.create_session(session_id, prompt_bundle)
        append_runtime_result(state, task["id"], session_id, result)
        return record

    @router.get("/tasks/{task_id}/sessions", response_model=list[SessionResponse])
    def list_task_sessions(task_id: str) -> list[dict[str, Any]]:
        require_task(state, task_id)
        return [s for s in state.list_sessions() if s["task_id"] == task_id]

    @router.post("/tasks/{task_id}/inputs/text", response_model=ImportedInputResponse)
    def add_text_input(task_id: str, request: ImportTextRequest) -> dict[str, Any]:
        task = require_task(state, task_id)
        result = import_text_input(
            Path(task["workspace_root"]),
            request.name,
            request.content,
            utc_now(),
        )
        sessions = [s for s in state.list_sessions() if s["task_id"] == task_id]
        if sessions:
            # Attach to most recent session by updated_at rather than first/oldest
            latest = max(sessions, key=lambda s: s.get("updated_at", ""))
            event = manual_event(
                task_id,
                latest["id"],
                f"convert-input-{result['id']}",
                TimelineActor.SYSTEM,
                SemanticEventKind.CONVERT_INPUT,
                "Convert input to Markdown",
                [result["markdown_path"], result["conversion_report_path"]],
            )
            state.append_timeline_event(latest["id"], asdict(event))
            result["event"] = asdict(event)
        return result

    return router
```

Note the `add_text_input` above also fixes **C4** (attaches to most recent session instead of `sessions[0]`).

Full `routes/sessions.py`:

```python
# services/api/docagent_api/routes/sessions.py
from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Response

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
from docagent_api.time import utc_now
from docagent_contracts import RuntimeSessionState, SemanticEventKind, TimelineActor


def create_sessions_router(state: DocAgentState, adapter: Any) -> APIRouter:
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
                state, task["id"], session, RuntimeSessionState.RUNNING_CONTEXT, operation,
            )
        result = run_runtime_operation(
            state, session, RuntimeSessionState.RUNNING_CONTEXT, lambda: adapter.start_loop(session_id),
        )
        append_runtime_result(state, task["id"], session_id, result)
        set_session_state(state, session, result.next_state)
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
        from pathlib import Path
        prepare_transition(state, session, RuntimeSessionState.RUNNING_DRAFT)
        (Path(task["workspace_root"]) / "draft" / "outline.md").write_text(
            request.outline_markdown if request.outline_markdown.endswith("\n") else f"{request.outline_markdown}\n",
            encoding="utf-8",
        )
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
                previous_state_on_failure=RuntimeSessionState.AWAIT_OUTLINE_APPROVAL,
                transition_prepared=True,
            )
        try:
            result = adapter.approve_outline(session_id)
        except Exception as exc:
            set_session_state(state, session, RuntimeSessionState.AWAIT_OUTLINE_APPROVAL)
            raise HTTPException(status_code=502, detail=f"Runtime operation failed: {exc}") from exc
        append_runtime_result(state, task["id"], session_id, result)
        set_session_state(state, session, result.next_state)
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
            prepare_transition(state, session, RuntimeSessionState.RUNNING_REVISION)
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
                    previous_state_on_failure=previous_state, transition_prepared=True,
                )
            result = adapter.revise_selection(session_id, request.selected_text, request.instruction)
        except HTTPException:
            raise
        except FileNotFoundError as exc:
            set_session_state(state, session, previous_state)
            raise HTTPException(status_code=400, detail="Draft does not exist. Approve the outline first.") from exc
        except ValueError as exc:
            set_session_state(state, session, previous_state)
            raise HTTPException(status_code=422, detail="Selected text not found in draft.") from exc
        except Exception as exc:
            set_session_state(state, session, previous_state)
            raise HTTPException(status_code=502, detail=f"Runtime operation failed: {exc}") from exc
        append_runtime_result(state, task["id"], session_id, result)
        set_session_state(state, session, result.next_state)
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
                state, task["id"], session, RuntimeSessionState.RUNNING_CHECKLIST, operation,
            )
        result = run_runtime_operation(
            state, session, RuntimeSessionState.RUNNING_CHECKLIST, lambda: adapter.run_checklist(session_id),
        )
        append_runtime_result(state, task["id"], session_id, result)
        set_session_state(state, session, result.next_state)
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
                state, task["id"], session, RuntimeSessionState.RUNNING_EXPORT, operation,
            )
        result = run_runtime_operation(
            state, session, RuntimeSessionState.RUNNING_EXPORT, lambda: adapter.export_markdown(session_id),
        )
        append_runtime_result(state, task["id"], session_id, result)
        set_session_state(state, session, result.next_state)
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
        if background:
            user_event = manual_event(
                task["id"], session_id, f"user-{uuid4().hex[:8]}",
                TimelineActor.USER, SemanticEventKind.USER_MESSAGE, request.message, [],
            )
            state.append_timeline_event(session_id, asdict(user_event))
            stream_method = getattr(adapter, "send_message_stream", None)
            if callable(stream_method):
                operation = lambda: stream_method(
                    session_id, request.message,
                    runtime_event_sink(state, task["id"], session_id),
                )
            else:
                operation = lambda: adapter.send_message(session_id, request.message)
            response.status_code = 202
            return start_background_runtime_operation(
                state, task["id"], session, RuntimeSessionState.RUNNING_CHAT, operation,
            )
        result = run_runtime_operation(
            state, session, RuntimeSessionState.RUNNING_CHAT,
            lambda: adapter.send_message(session_id, request.message),
        )
        append_runtime_result(state, task["id"], session_id, result)
        if not result.events:
            user_event = manual_event(
                task["id"], session_id, f"user-{uuid4().hex[:8]}",
                TimelineActor.USER, SemanticEventKind.USER_MESSAGE, request.message, [],
            )
            state.append_timeline_event(session_id, asdict(user_event))
        set_session_state(state, session, result.next_state)
        return {"session_id": session_id, "event_count": len(result.events)}

    @router.post("/sessions/{session_id}/cancel", response_model=LoopActionResponse)
    def cancel_session(session_id: str) -> dict[str, Any]:
        session = require_session(state, session_id)
        task = require_task(state, session["task_id"])
        previous_state = RuntimeSessionState(session["status"])
        prepare_transition(state, session, RuntimeSessionState.CANCELLED)
        try:
            result = adapter.cancel(session_id)
        except HTTPException:
            set_session_state(state, session, previous_state)
            raise
        except Exception as exc:
            set_session_state(state, session, previous_state)
            raise HTTPException(status_code=502, detail=f"Runtime cancel failed: {exc}") from exc
        append_runtime_result(state, task["id"], session_id, result)
        set_session_state(state, session, result.next_state)
        return runtime_result_response(result)

    @router.get("/sessions/{session_id}/timeline", response_model=list[TimelineEventResponse])
    def get_timeline(session_id: str) -> list[dict[str, Any]]:
        if state.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return state.list_timeline_events(session_id)

    return router
```

- [ ] **Step 6: Reduce app.py to factory + health + router includes**

Replace the content of `services/api/docagent_api/app.py` with:

```python
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from docagent_api.response_models import HealthResponse
from docagent_api.routes.doctypes import create_doctypes_router
from docagent_api.routes.sessions import create_sessions_router
from docagent_api.routes.tasks import create_tasks_router
from docagent_api.runtime_factory import create_runtime_adapter
from docagent_api.session_state import InvalidSessionTransition, require_transition
from docagent_api.state import DocAgentState
from docagent_api.time import utc_now
from docagent_contracts import RuntimeSessionState


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

    app.include_router(create_doctypes_router(root))
    app.include_router(create_tasks_router(state, adapter, root))
    app.include_router(create_sessions_router(state, adapter))

    return app


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
            session["status"] = RuntimeSessionState.FAILED.value
            session["updated_at"] = utc_now()
            state.save_session(session)


def state_root_from_env() -> Path | None:
    value = os.environ.get("DOCAGENT_STATE_ROOT")
    return Path(value) if value else None


app = create_app(state_root=state_root_from_env())
```

- [ ] **Step 7: Run all tests**

```bash
python -m pytest services/api/tests/ -q
```

Expected: all 34+ tests pass. If any test imports `_require_task`, `_normalize_task`, or other private helpers from `app.py` via monkeypatch, update those imports to use the new locations.

- [ ] **Step 8: Commit**

```bash
git add services/api/docagent_api/ services/api/tests/
git commit -m "Split app.py into focused route modules (I1); move request models to request_models.py"
```

---

## Out of Scope (separate plans)

- **Assistant-UI integration** (Phase A–C from the review) — requires its own brainstorm + plan
- **Phase 0 completion** (tools/export, PRD examples/specs) — separate plan
- **I2 partial**: `add_text_input` session attachment fix (C4) is already fixed in Task 5 above (`max` by `updated_at`)
