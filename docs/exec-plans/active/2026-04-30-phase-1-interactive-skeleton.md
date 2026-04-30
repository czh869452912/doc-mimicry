# Phase 1 Interactive Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first interactive product skeleton: FastAPI endpoints, file-backed state, a mock runtime adapter, semantic timeline persistence, and a thin React workbench UI.

**Architecture:** Use an API-first vertical slice. `services/api` owns product state and workspace orchestration, `agent/runtime-adapters/mock` simulates runtime behavior through the same boundary a real runtime will use, and `apps/web` consumes API contracts without reading repository files directly.

**Tech Stack:** Python 3.11, FastAPI, pytest, standard-library file-backed JSON state, React + Vite + TypeScript for the thin UI.

---

## Files And Responsibilities

- `pyproject.toml`: add API runtime and test dependencies, extend pytest pythonpath with `services/api` and `agent/runtime-adapters/mock`.
- `.gitignore`: ignore `.local/`, frontend dependency/build outputs, and Vite env files.
- `services/api/docagent_api/models.py`: API request/response dataclasses or typed dictionaries aligned with shared contracts.
- `services/api/docagent_api/state.py`: file-backed task, session, and timeline persistence rooted at `.local/docagent` by default.
- `services/api/docagent_api/doctypes.py`: read doc-type pack metadata and converted-resource directories from `doc-types/`.
- `services/api/docagent_api/drafts.py`: read and update `draft/draft.md` inside task workspaces.
- `services/api/docagent_api/app.py`: FastAPI app and endpoint wiring.
- `services/api/tests/test_api.py`: API tests for health, doc types, task creation, sessions, messages, timeline, and draft roundtrip.
- `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py`: deterministic mock runtime adapter that writes context, outline, draft, checkpoints, and semantic timeline events.
- `agent/runtime-adapters/mock/tests/test_adapter.py`: adapter tests with temporary workspaces and state.
- `apps/web/package.json`: Vite React scripts and dependencies.
- `apps/web/index.html`: Vite entry point.
- `apps/web/src/api.ts`: typed API client used by UI pages.
- `apps/web/src/types.ts`: TypeScript interfaces matching Phase 1 API payloads.
- `apps/web/src/App.tsx`: route shell for management and workbench pages.
- `apps/web/src/pages/ManagementPage.tsx`: minimal doc-type dashboard.
- `apps/web/src/pages/WorkbenchPage.tsx`: three-column authoring surface.
- `apps/web/src/styles.css`: dense operational styling for management and authoring surfaces.
- `.github/workflows/ci.yml`: run Python API/runtime tests and frontend install/build/test checks.
- `docs/quality/testing.md`: document Phase 1 local verification commands.

## Task 1: API Dependencies And State Skeleton

**Files:**
- Modify: `pyproject.toml`
- Modify: `.gitignore`
- Create: `services/api/docagent_api/__init__.py`
- Create: `services/api/docagent_api/models.py`
- Create: `services/api/docagent_api/state.py`
- Test: `services/api/tests/test_state.py`

- [ ] **Step 1: Write failing state tests**

Create `services/api/tests/test_state.py`:

```python
from pathlib import Path

from docagent_api.state import DocAgentState


def test_state_starts_with_empty_collections(tmp_path: Path) -> None:
    state = DocAgentState(tmp_path)

    assert state.list_tasks() == []
    assert state.list_sessions() == []


def test_state_persists_task_and_session(tmp_path: Path) -> None:
    state = DocAgentState(tmp_path)
    task = {
        "id": "task-001",
        "doc_type_id": "prd",
        "brief": "Draft a PRD",
        "workspace_root": "workspaces/task-001",
        "created_at": "2026-04-30T00:00:00Z",
        "updated_at": "2026-04-30T00:00:00Z",
    }
    session = {
        "id": "session-001",
        "task_id": "task-001",
        "status": "idle",
        "created_at": "2026-04-30T00:00:00Z",
        "updated_at": "2026-04-30T00:00:00Z",
    }

    state.save_task(task)
    state.save_session(session)
    reloaded = DocAgentState(tmp_path)

    assert reloaded.get_task("task-001") == task
    assert reloaded.get_session("session-001") == session
```

- [ ] **Step 2: Run state tests to verify they fail**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest services/api/tests/test_state.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'docagent_api'`.

- [ ] **Step 3: Add dependencies and state implementation**

Modify `pyproject.toml`:

```toml
[project]
name = "docagent-workbench"
version = "0.0.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn>=0.30.0",
]

[tool.pytest.ini_options]
pythonpath = [
  "packages/contracts",
  "packages/workspace",
  "packages/timeline",
  "tools/import",
  "services/api",
  "agent/runtime-adapters/mock"
]
testpaths = [
  "packages",
  "tools",
  "services/api/tests",
  "agent/runtime-adapters/mock/tests"
]
```

Modify `.gitignore`:

```gitignore
__pycache__/
*.py[cod]
.pytest_cache/
.venv/
venv/
.local/
node_modules/
dist/
.vite/
.env.local
```

Create `services/api/docagent_api/__init__.py`:

```python
"""FastAPI backend for DocAgent Workbench."""
```

Create `services/api/docagent_api/models.py`:

```python
from __future__ import annotations

from typing import Literal, TypedDict


class TaskRecord(TypedDict):
    id: str
    doc_type_id: str
    brief: str
    workspace_root: str
    created_at: str
    updated_at: str


class SessionRecord(TypedDict):
    id: str
    task_id: str
    status: Literal["idle", "running", "paused", "completed", "failed"]
    created_at: str
    updated_at: str
```

Create `services/api/docagent_api/state.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class DocAgentState:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "timelines").mkdir(parents=True, exist_ok=True)
        (self.root / "workspaces").mkdir(parents=True, exist_ok=True)

    def list_tasks(self) -> list[dict[str, Any]]:
        return list(self._read_map("tasks.json").values())

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        return self._read_map("tasks.json").get(task_id)

    def save_task(self, task: dict[str, Any]) -> None:
        tasks = self._read_map("tasks.json")
        tasks[task["id"]] = task
        self._write_map("tasks.json", tasks)

    def list_sessions(self) -> list[dict[str, Any]]:
        return list(self._read_map("sessions.json").values())

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        return self._read_map("sessions.json").get(session_id)

    def save_session(self, session: dict[str, Any]) -> None:
        sessions = self._read_map("sessions.json")
        sessions[session["id"]] = session
        self._write_map("sessions.json", sessions)

    def append_timeline_event(self, session_id: str, event: dict[str, Any]) -> None:
        events = self.list_timeline_events(session_id)
        events.append(event)
        self._timeline_path(session_id).write_text(
            json.dumps(events, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def list_timeline_events(self, session_id: str) -> list[dict[str, Any]]:
        path = self._timeline_path(session_id)
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def workspace_root(self, task_id: str) -> Path:
        return self.root / "workspaces" / task_id

    def _read_map(self, filename: str) -> dict[str, Any]:
        path = self.root / filename
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_map(self, filename: str, data: dict[str, Any]) -> None:
        (self.root / filename).write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def _timeline_path(self, session_id: str) -> Path:
        return self.root / "timelines" / f"{session_id}.json"
```

- [ ] **Step 4: Run state tests to verify they pass**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest services/api/tests/test_state.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add pyproject.toml .gitignore services/api/docagent_api services/api/tests/test_state.py
git commit -m "Add API state foundation"
```

## Task 2: DocType Discovery And Draft Helpers

**Files:**
- Create: `services/api/docagent_api/doctypes.py`
- Create: `services/api/docagent_api/drafts.py`
- Test: `services/api/tests/test_doctypes_and_drafts.py`

- [ ] **Step 1: Write failing doctypes and drafts tests**

Create `services/api/tests/test_doctypes_and_drafts.py`:

```python
from pathlib import Path

from docagent_api.doctypes import get_doc_type, list_doc_types
from docagent_api.drafts import read_draft, write_draft


def test_lists_seed_prd_doc_type() -> None:
    doc_types = list_doc_types(Path("doc-types"))

    assert doc_types[0]["id"] == "prd"
    assert doc_types[0]["has_skill"] is True
    assert "examples" in doc_types[0]["resource_groups"]


def test_reads_prd_doc_type_detail() -> None:
    detail = get_doc_type(Path("doc-types"), "prd")

    assert detail is not None
    assert detail["id"] == "prd"
    assert "skill_markdown" in detail
    assert "checklists" in detail["resource_groups"]


def test_draft_read_write_roundtrip(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"

    write_draft(workspace, "# Draft\n\nHello")

    assert read_draft(workspace) == "# Draft\n\nHello\n"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest services/api/tests/test_doctypes_and_drafts.py -q
```

Expected: FAIL with imports missing for `docagent_api.doctypes` and `docagent_api.drafts`.

- [ ] **Step 3: Implement doctypes and drafts helpers**

Create `services/api/docagent_api/doctypes.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any


RESOURCE_GROUPS = ["examples", "specs", "checklists", "export-references"]


def list_doc_types(root: Path) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    return [summarize_doc_type(path) for path in sorted(root.iterdir()) if path.is_dir()]


def get_doc_type(root: Path, doc_type_id: str) -> dict[str, Any] | None:
    path = root / doc_type_id
    if not path.exists() or not path.is_dir():
        return None
    detail = summarize_doc_type(path)
    skill_path = path / "SKILL.md"
    detail["skill_markdown"] = skill_path.read_text(encoding="utf-8") if skill_path.exists() else ""
    return detail


def summarize_doc_type(path: Path) -> dict[str, Any]:
    return {
        "id": path.name,
        "title": path.name.upper(),
        "has_skill": (path / "SKILL.md").exists(),
        "resource_groups": {
            group: _list_group(path / group)
            for group in RESOURCE_GROUPS
        },
    }


def _list_group(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [
        item.relative_to(path).as_posix()
        for item in sorted(path.rglob("*"))
        if item.is_file() and item.name != ".gitkeep"
    ]
```

Create `services/api/docagent_api/drafts.py`:

```python
from __future__ import annotations

from pathlib import Path


def read_draft(workspace_root: Path) -> str:
    path = workspace_root / "draft" / "draft.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_draft(workspace_root: Path, markdown: str) -> None:
    path = workspace_root / "draft" / "draft.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = markdown if markdown.endswith("\n") else f"{markdown}\n"
    path.write_text(text, encoding="utf-8")
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest services/api/tests/test_doctypes_and_drafts.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add services/api/docagent_api/doctypes.py services/api/docagent_api/drafts.py services/api/tests/test_doctypes_and_drafts.py
git commit -m "Add doc type and draft helpers"
```

## Task 3: Mock Runtime Adapter

**Files:**
- Create: `agent/runtime-adapters/mock/docagent_mock_runtime/__init__.py`
- Create: `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py`
- Test: `agent/runtime-adapters/mock/tests/test_adapter.py`

- [ ] **Step 1: Write failing adapter tests**

Create `agent/runtime-adapters/mock/tests/test_adapter.py`:

```python
from pathlib import Path

from docagent_mock_runtime.adapter import MockRuntimeAdapter


def test_first_message_creates_context_outline_draft_and_events(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "brief.md").write_text("Create a pricing PRD\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()
    events = adapter.send_message(
        task_id="task-001",
        session_id="session-001",
        workspace_root=workspace,
        message="Start drafting",
    )

    assert (workspace / "context" / "user_intent.md").exists()
    assert (workspace / "context" / "style_notes.md").exists()
    assert (workspace / "context" / "structure_notes.md").exists()
    assert (workspace / "draft" / "outline.md").exists()
    assert "# PRD Draft" in (workspace / "draft" / "draft.md").read_text(encoding="utf-8")
    assert [event.kind.value for event in events] == [
        "user_message",
        "read_skill",
        "extract_style",
        "extract_structure",
        "generate_outline",
        "update_draft",
    ]


def test_later_message_checkpoints_and_updates_draft(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "draft").mkdir(parents=True)
    (workspace / "draft" / "draft.md").write_text("# Existing\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()
    events = adapter.send_message(
        task_id="task-001",
        session_id="session-001",
        workspace_root=workspace,
        message="Tighten the launch section",
    )

    assert (workspace / "versions" / "v001.md").exists()
    assert "Revision note" in (workspace / "draft" / "draft.md").read_text(encoding="utf-8")
    assert [event.kind.value for event in events] == [
        "user_message",
        "create_checkpoint",
        "update_draft",
    ]
```

- [ ] **Step 2: Run adapter tests to verify they fail**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest agent/runtime-adapters/mock/tests/test_adapter.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'docagent_mock_runtime'`.

- [ ] **Step 3: Implement mock runtime adapter**

Create `agent/runtime-adapters/mock/docagent_mock_runtime/__init__.py`:

```python
"""Mock runtime adapter used by Phase 1 API and UI skeleton."""
```

Create `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py`:

```python
from __future__ import annotations

from pathlib import Path

from docagent_contracts import (
    SemanticEventKind,
    SemanticTimelineEvent,
    TimelineActor,
    TimelineStatus,
)
from docagent_workspace import checkpoint_draft


class MockRuntimeAdapter:
    def send_message(
        self,
        task_id: str,
        session_id: str,
        workspace_root: Path,
        message: str,
    ) -> list[SemanticTimelineEvent]:
        if (workspace_root / "draft" / "draft.md").exists():
            return self._revise(task_id, session_id, workspace_root, message)
        return self._first_draft(task_id, session_id, workspace_root, message)

    def _first_draft(
        self,
        task_id: str,
        session_id: str,
        workspace_root: Path,
        message: str,
    ) -> list[SemanticTimelineEvent]:
        (workspace_root / "context").mkdir(parents=True, exist_ok=True)
        (workspace_root / "draft").mkdir(parents=True, exist_ok=True)
        brief = _read_text(workspace_root / "brief.md")
        (workspace_root / "context" / "user_intent.md").write_text(
            f"# User Intent\n\n{brief}",
            encoding="utf-8",
        )
        (workspace_root / "context" / "style_notes.md").write_text(
            "# Style Notes\n\nMirror structure and narration patterns from converted Markdown examples.\n",
            encoding="utf-8",
        )
        (workspace_root / "context" / "structure_notes.md").write_text(
            "# Structure Notes\n\nUse a concise PRD structure with goals, users, requirements, and risks.\n",
            encoding="utf-8",
        )
        (workspace_root / "draft" / "outline.md").write_text(
            "# Outline\n\n1. Background\n2. Goals\n3. Requirements\n4. Risks\n",
            encoding="utf-8",
        )
        (workspace_root / "draft" / "draft.md").write_text(
            "# PRD Draft\n\n"
            "## Background\n\n"
            f"{brief.strip()}\n\n"
            "## Goals\n\n- Clarify the product outcome.\n\n"
            "## Requirements\n\n- Capture the first usable behavior.\n\n"
            "## Risks\n\n- Validate assumptions with users.\n",
            encoding="utf-8",
        )
        return [
            _event(task_id, session_id, "user-1", TimelineActor.USER, SemanticEventKind.USER_MESSAGE, message, []),
            _event(task_id, session_id, "skill-1", TimelineActor.AGENT, SemanticEventKind.READ_SKILL, "Read document type skill", ["doc-types/prd/SKILL.md"]),
            _event(task_id, session_id, "style-1", TimelineActor.AGENT, SemanticEventKind.EXTRACT_STYLE, "Extract style notes", ["context/style_notes.md"]),
            _event(task_id, session_id, "structure-1", TimelineActor.AGENT, SemanticEventKind.EXTRACT_STRUCTURE, "Extract structure notes", ["context/structure_notes.md"]),
            _event(task_id, session_id, "outline-1", TimelineActor.AGENT, SemanticEventKind.GENERATE_OUTLINE, "Generate outline", ["draft/outline.md"]),
            _event(task_id, session_id, "draft-1", TimelineActor.AGENT, SemanticEventKind.UPDATE_DRAFT, "Update draft", ["draft/draft.md"]),
        ]

    def _revise(
        self,
        task_id: str,
        session_id: str,
        workspace_root: Path,
        message: str,
    ) -> list[SemanticTimelineEvent]:
        checkpoint_draft(workspace_root, summary=f"Before revision: {message}")
        draft_path = workspace_root / "draft" / "draft.md"
        current = _read_text(draft_path)
        draft_path.write_text(
            current.rstrip() + f"\n\n## Revision note\n\n{message}\n",
            encoding="utf-8",
        )
        return [
            _event(task_id, session_id, "user-2", TimelineActor.USER, SemanticEventKind.USER_MESSAGE, message, []),
            _event(task_id, session_id, "checkpoint-1", TimelineActor.SYSTEM, SemanticEventKind.CREATE_CHECKPOINT, "Create checkpoint", ["versions/v001.md"]),
            _event(task_id, session_id, "draft-2", TimelineActor.AGENT, SemanticEventKind.UPDATE_DRAFT, "Update draft", ["draft/draft.md"]),
        ]


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _event(
    task_id: str,
    session_id: str,
    suffix: str,
    actor: TimelineActor,
    kind: SemanticEventKind,
    summary: str,
    paths: list[str],
) -> SemanticTimelineEvent:
    return SemanticTimelineEvent(
        id=f"{session_id}-{suffix}",
        session_id=session_id,
        task_id=task_id,
        actor=actor,
        kind=kind,
        raw_event_id=None,
        summary=summary,
        paths=paths,
        status=TimelineStatus.SUCCEEDED,
        created_at="2026-04-30T00:00:00Z",
    )
```

- [ ] **Step 4: Run adapter tests to verify they pass**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest agent/runtime-adapters/mock/tests/test_adapter.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add agent/runtime-adapters/mock/docagent_mock_runtime agent/runtime-adapters/mock/tests/test_adapter.py pyproject.toml
git commit -m "Add mock runtime adapter"
```

## Task 4: FastAPI App Endpoints

**Files:**
- Create: `services/api/docagent_api/app.py`
- Modify: `services/api/README.md`
- Test: `services/api/tests/test_api.py`

- [ ] **Step 1: Write failing API tests**

Create `services/api/tests/test_api.py`:

```python
from pathlib import Path

from fastapi.testclient import TestClient

from docagent_api.app import create_app


def test_health_endpoint(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_doc_type_endpoints(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))

    listing = client.get("/doc-types")
    detail = client.get("/doc-types/prd")

    assert listing.status_code == 200
    assert listing.json()[0]["id"] == "prd"
    assert detail.status_code == 200
    assert detail.json()["id"] == "prd"
    assert "skill_markdown" in detail.json()


def test_task_session_message_timeline_and_draft_roundtrip(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))

    task_response = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build billing controls"})
    assert task_response.status_code == 200
    task = task_response.json()

    session_response = client.post(f"/tasks/{task['id']}/sessions")
    assert session_response.status_code == 200
    session = session_response.json()

    message_response = client.post(
        f"/sessions/{session['id']}/messages",
        json={"message": "Start the PRD"},
    )
    assert message_response.status_code == 200
    assert message_response.json()["event_count"] == 6

    timeline = client.get(f"/sessions/{session['id']}/timeline").json()
    assert [event["kind"] for event in timeline] == [
        "user_message",
        "read_skill",
        "extract_style",
        "extract_structure",
        "generate_outline",
        "update_draft",
    ]

    draft = client.get(f"/tasks/{task['id']}/draft").json()
    assert "# PRD Draft" in draft["markdown"]

    update_response = client.put(f"/tasks/{task['id']}/draft", json={"markdown": "# Edited\n"})
    assert update_response.status_code == 200
    assert client.get(f"/tasks/{task['id']}/draft").json()["markdown"] == "# Edited\n"
```

- [ ] **Step 2: Run API tests to verify they fail**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest services/api/tests/test_api.py -q
```

Expected: FAIL because `docagent_api.app` does not exist.

- [ ] **Step 3: Install FastAPI test dependency if missing**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pip install fastapi uvicorn httpx
```

Expected: dependencies are available for local tests.

- [ ] **Step 4: Implement FastAPI app**

Create `services/api/docagent_api/app.py`:

```python
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from docagent_api.doctypes import get_doc_type, list_doc_types
from docagent_api.drafts import read_draft, write_draft
from docagent_api.state import DocAgentState
from docagent_mock_runtime.adapter import MockRuntimeAdapter
from docagent_workspace import create_workspace


class CreateTaskRequest(BaseModel):
    doc_type_id: str
    brief: str


class SendMessageRequest(BaseModel):
    message: str


class UpdateDraftRequest(BaseModel):
    markdown: str


def create_app(state_root: Path | None = None, repo_root: Path | None = None) -> FastAPI:
    app = FastAPI(title="DocAgent Workbench API")
    root = repo_root or Path.cwd()
    state = DocAgentState(state_root or root / ".local" / "docagent")
    adapter = MockRuntimeAdapter()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/doc-types")
    def doc_types() -> list[dict[str, object]]:
        return list_doc_types(root / "doc-types")

    @app.get("/doc-types/{doc_type_id}")
    def doc_type_detail(doc_type_id: str) -> dict[str, object]:
        detail = get_doc_type(root / "doc-types", doc_type_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Document type not found")
        return detail

    @app.post("/tasks")
    def create_task(request: CreateTaskRequest) -> dict[str, str]:
        if get_doc_type(root / "doc-types", request.doc_type_id) is None:
            raise HTTPException(status_code=404, detail="Document type not found")
        task_id = f"task-{uuid4().hex[:8]}"
        workspace_root = state.workspace_root(task_id)
        create_workspace(workspace_root, request.brief)
        record = {
            "id": task_id,
            "doc_type_id": request.doc_type_id,
            "brief": request.brief,
            "workspace_root": str(workspace_root),
            "created_at": "2026-04-30T00:00:00Z",
            "updated_at": "2026-04-30T00:00:00Z",
        }
        state.save_task(record)
        return record

    @app.get("/tasks/{task_id}")
    def get_task(task_id: str) -> dict[str, object]:
        task = state.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return task

    @app.get("/tasks/{task_id}/workspace")
    def get_workspace(task_id: str) -> dict[str, object]:
        task = _require_task(state, task_id)
        workspace_root = Path(task["workspace_root"])
        files = [
            path.relative_to(workspace_root).as_posix()
            for path in sorted(workspace_root.rglob("*"))
            if path.is_file()
        ]
        return {"task_id": task_id, "root": str(workspace_root), "files": files}

    @app.get("/tasks/{task_id}/draft")
    def get_draft(task_id: str) -> dict[str, str]:
        task = _require_task(state, task_id)
        return {"task_id": task_id, "markdown": read_draft(Path(task["workspace_root"]))}

    @app.put("/tasks/{task_id}/draft")
    def update_draft(task_id: str, request: UpdateDraftRequest) -> dict[str, str]:
        task = _require_task(state, task_id)
        write_draft(Path(task["workspace_root"]), request.markdown)
        return {"task_id": task_id, "markdown": read_draft(Path(task["workspace_root"]))}

    @app.post("/tasks/{task_id}/sessions")
    def create_session(task_id: str) -> dict[str, str]:
        _require_task(state, task_id)
        session_id = f"session-{uuid4().hex[:8]}"
        record = {
            "id": session_id,
            "task_id": task_id,
            "status": "idle",
            "created_at": "2026-04-30T00:00:00Z",
            "updated_at": "2026-04-30T00:00:00Z",
        }
        state.save_session(record)
        return record

    @app.get("/sessions/{session_id}")
    def get_session(session_id: str) -> dict[str, object]:
        session = state.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return session

    @app.post("/sessions/{session_id}/messages")
    def send_message(session_id: str, request: SendMessageRequest) -> dict[str, object]:
        session = state.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        task = _require_task(state, session["task_id"])
        events = adapter.send_message(
            task_id=task["id"],
            session_id=session_id,
            workspace_root=Path(task["workspace_root"]),
            message=request.message,
        )
        for event in events:
            state.append_timeline_event(session_id, asdict(event))
        return {"session_id": session_id, "event_count": len(events)}

    @app.get("/sessions/{session_id}/timeline")
    def get_timeline(session_id: str) -> list[dict[str, object]]:
        if state.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return state.list_timeline_events(session_id)

    return app


def _require_task(state: DocAgentState, task_id: str) -> dict[str, object]:
    task = state.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


app = create_app()
```

Modify `services/api/README.md` by adding:

```markdown
## Phase 1 Local Run

```powershell
uvicorn docagent_api.app:app --reload --app-dir services/api
```
```

- [ ] **Step 5: Run API tests to verify they pass**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest services/api/tests/test_api.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add services/api/docagent_api/app.py services/api/README.md services/api/tests/test_api.py
git commit -m "Add Phase 1 API endpoints"
```

## Task 5: React Web Skeleton

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/index.html`
- Create: `apps/web/src/main.tsx`
- Create: `apps/web/src/App.tsx`
- Create: `apps/web/src/api.ts`
- Create: `apps/web/src/types.ts`
- Create: `apps/web/src/pages/ManagementPage.tsx`
- Create: `apps/web/src/pages/WorkbenchPage.tsx`
- Create: `apps/web/src/styles.css`
- Modify: `apps/web/README.md`

- [ ] **Step 1: Create frontend package and source files**

Create `apps/web/package.json`:

```json
{
  "name": "docagent-web",
  "version": "0.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 127.0.0.1",
    "build": "tsc --noEmit && vite build",
    "test": "tsc --noEmit"
  },
  "dependencies": {
    "@vitejs/plugin-react": "^5.0.0",
    "vite": "^7.0.0",
    "typescript": "^5.8.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "lucide-react": "^0.468.0"
  },
  "devDependencies": {}
}
```

Create `apps/web/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>DocAgent Workbench</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Create `apps/web/src/types.ts`:

```typescript
export interface DocTypeSummary {
  id: string;
  title: string;
  has_skill: boolean;
  resource_groups: Record<string, string[]>;
  skill_markdown?: string;
}

export interface TaskRecord {
  id: string;
  doc_type_id: string;
  brief: string;
  workspace_root: string;
}

export interface SessionRecord {
  id: string;
  task_id: string;
  status: string;
}

export interface TimelineEvent {
  id: string;
  actor: string;
  kind: string;
  summary: string;
  paths: string[];
  status: string;
}
```

Create `apps/web/src/api.ts`:

```typescript
import type { DocTypeSummary, SessionRecord, TaskRecord, TimelineEvent } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  listDocTypes: () => request<DocTypeSummary[]>("/doc-types"),
  getDocType: (id: string) => request<DocTypeSummary>(`/doc-types/${id}`),
  createTask: (doc_type_id: string, brief: string) =>
    request<TaskRecord>("/tasks", {
      method: "POST",
      body: JSON.stringify({ doc_type_id, brief }),
    }),
  createSession: (taskId: string) =>
    request<SessionRecord>(`/tasks/${taskId}/sessions`, { method: "POST" }),
  sendMessage: (sessionId: string, message: string) =>
    request<{ event_count: number }>(`/sessions/${sessionId}/messages`, {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
  getTimeline: (sessionId: string) => request<TimelineEvent[]>(`/sessions/${sessionId}/timeline`),
  getDraft: (taskId: string) => request<{ markdown: string }>(`/tasks/${taskId}/draft`),
  updateDraft: (taskId: string, markdown: string) =>
    request<{ markdown: string }>(`/tasks/${taskId}/draft`, {
      method: "PUT",
      body: JSON.stringify({ markdown }),
    }),
};
```

Create `apps/web/src/main.tsx`:

```typescript
import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

Create `apps/web/src/App.tsx`:

```typescript
import { LayoutDashboard, PanelsTopLeft } from "lucide-react";
import { useState } from "react";
import { ManagementPage } from "./pages/ManagementPage";
import { WorkbenchPage } from "./pages/WorkbenchPage";

type Page = "management" | "workbench";

export function App() {
  const [page, setPage] = useState<Page>("workbench");

  return (
    <main className="app-shell">
      <nav className="topbar">
        <strong>DocAgent Workbench</strong>
        <button className={page === "workbench" ? "active" : ""} onClick={() => setPage("workbench")}>
          <PanelsTopLeft size={16} /> Workbench
        </button>
        <button className={page === "management" ? "active" : ""} onClick={() => setPage("management")}>
          <LayoutDashboard size={16} /> Management
        </button>
      </nav>
      {page === "management" ? <ManagementPage /> : <WorkbenchPage />}
    </main>
  );
}
```

Create `apps/web/src/pages/ManagementPage.tsx`:

```typescript
import { useEffect, useState } from "react";
import { api } from "../api";
import type { DocTypeSummary } from "../types";

export function ManagementPage() {
  const [docTypes, setDocTypes] = useState<DocTypeSummary[]>([]);
  const [selected, setSelected] = useState<DocTypeSummary | null>(null);

  useEffect(() => {
    api.listDocTypes().then(async (items) => {
      setDocTypes(items);
      if (items[0]) {
        setSelected(await api.getDocType(items[0].id));
      }
    });
  }, []);

  return (
    <section className="management-grid">
      <aside className="panel">
        <h1>Doc types</h1>
        {docTypes.map((docType) => (
          <button key={docType.id} onClick={() => api.getDocType(docType.id).then(setSelected)}>
            {docType.title}
          </button>
        ))}
      </aside>
      <section className="panel detail-panel">
        <h2>{selected?.title ?? "No document type selected"}</h2>
        <div className="resource-grid">
          {selected &&
            Object.entries(selected.resource_groups).map(([group, files]) => (
              <section key={group}>
                <h3>{group}</h3>
                {files.length === 0 ? <p className="muted">No files</p> : files.map((file) => <p key={file}>{file}</p>)}
              </section>
            ))}
        </div>
        <h3>SKILL.md</h3>
        <pre>{selected?.skill_markdown ?? ""}</pre>
      </section>
      <aside className="panel">
        <h2>Skill Creator</h2>
        <p className="muted">Conversation placeholder for building and revising document type packs.</p>
      </aside>
    </section>
  );
}
```

Create `apps/web/src/pages/WorkbenchPage.tsx`:

```typescript
import { Send, Save } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import type { DocTypeSummary, SessionRecord, TaskRecord, TimelineEvent } from "../types";

export function WorkbenchPage() {
  const [docTypes, setDocTypes] = useState<DocTypeSummary[]>([]);
  const [task, setTask] = useState<TaskRecord | null>(null);
  const [session, setSession] = useState<SessionRecord | null>(null);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [brief, setBrief] = useState("Write a PRD for the first usable document imitation loop.");
  const [message, setMessage] = useState("Start drafting from the brief.");
  const [draft, setDraft] = useState("");

  useEffect(() => {
    api.listDocTypes().then(setDocTypes);
  }, []);

  async function createTaskAndSession() {
    const createdTask = await api.createTask("prd", brief);
    const createdSession = await api.createSession(createdTask.id);
    setTask(createdTask);
    setSession(createdSession);
    setTimeline([]);
    setDraft("");
  }

  async function sendMessage() {
    if (!session || !task) return;
    await api.sendMessage(session.id, message);
    setTimeline(await api.getTimeline(session.id));
    setDraft((await api.getDraft(task.id)).markdown);
  }

  async function saveDraft() {
    if (!task) return;
    setDraft((await api.updateDraft(task.id, draft)).markdown);
  }

  return (
    <section className="workbench-grid">
      <aside className="panel rail">
        <h1>Workspace</h1>
        <label>Doc type</label>
        <select>
          {docTypes.map((docType) => (
            <option key={docType.id}>{docType.id}</option>
          ))}
        </select>
        <label>Brief</label>
        <textarea value={brief} onChange={(event) => setBrief(event.target.value)} />
        <button onClick={createTaskAndSession}>Create task</button>
        <div className="meta-list">
          <p>Task: {task?.id ?? "none"}</p>
          <p>Session: {session?.id ?? "none"}</p>
          <p>Inputs: markdown-first</p>
          <p>Versions: workspace-backed</p>
          <p>Artifacts: pending</p>
        </div>
      </aside>
      <section className="panel timeline">
        <h1>Timeline</h1>
        <div className="timeline-list">
          {timeline.map((event) => (
            <article key={event.id} className="timeline-event">
              <strong>{event.kind}</strong>
              <span>{event.actor}</span>
              <p>{event.summary}</p>
              {event.paths.length > 0 && <small>{event.paths.join(", ")}</small>}
            </article>
          ))}
        </div>
        <div className="composer">
          <input value={message} onChange={(event) => setMessage(event.target.value)} />
          <button onClick={sendMessage} disabled={!session}>
            <Send size={16} /> Send
          </button>
        </div>
      </section>
      <aside className="panel preview">
        <header>
          <h1>Draft</h1>
          <button onClick={saveDraft} disabled={!task}>
            <Save size={16} /> Save
          </button>
        </header>
        <textarea value={draft} onChange={(event) => setDraft(event.target.value)} />
        <section className="markdown-preview">
          {draft.split("\n").map((line, index) => (
            <p key={`${line}-${index}`}>{line || "\u00A0"}</p>
          ))}
        </section>
      </aside>
    </section>
  );
}
```

Create `apps/web/src/styles.css`:

```css
:root {
  color: #202124;
  background: #f6f7f8;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
}

button,
input,
select,
textarea {
  font: inherit;
}

button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1px solid #c9ced6;
  border-radius: 6px;
  background: #ffffff;
  color: #202124;
  min-height: 34px;
  padding: 6px 10px;
  cursor: pointer;
}

button.active,
button:hover {
  border-color: #4169a8;
  color: #1b4f92;
}

.app-shell {
  min-height: 100vh;
}

.topbar {
  height: 52px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  border-bottom: 1px solid #d8dde5;
  background: #ffffff;
}

.topbar strong {
  margin-right: auto;
}

.panel {
  min-width: 0;
  background: #ffffff;
  border-right: 1px solid #d8dde5;
  padding: 14px;
  overflow: auto;
}

.management-grid,
.workbench-grid {
  height: calc(100vh - 52px);
  display: grid;
}

.management-grid {
  grid-template-columns: 240px minmax(420px, 1fr) 320px;
}

.workbench-grid {
  grid-template-columns: 280px minmax(420px, 1fr) minmax(360px, 42vw);
}

h1,
h2,
h3,
p {
  margin-top: 0;
}

h1 {
  font-size: 18px;
}

h2 {
  font-size: 16px;
}

h3 {
  font-size: 13px;
  text-transform: uppercase;
  color: #596273;
}

.rail,
.timeline,
.preview {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

textarea {
  width: 100%;
  min-height: 110px;
  resize: vertical;
  border: 1px solid #c9ced6;
  border-radius: 6px;
  padding: 10px;
}

.preview textarea {
  min-height: 240px;
  font-family: "Cascadia Mono", Consolas, monospace;
}

.timeline-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow: auto;
}

.timeline-event {
  border: 1px solid #d8dde5;
  border-radius: 6px;
  padding: 10px;
  background: #fbfcfd;
}

.timeline-event span {
  margin-left: 8px;
  color: #596273;
}

.timeline-event small,
.muted {
  color: #6f7785;
}

.composer,
.preview header {
  display: flex;
  gap: 8px;
  align-items: center;
}

.composer input {
  flex: 1;
  border: 1px solid #c9ced6;
  border-radius: 6px;
  min-height: 34px;
  padding: 6px 10px;
}

.resource-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

pre,
.markdown-preview {
  border: 1px solid #d8dde5;
  border-radius: 6px;
  background: #fbfcfd;
  padding: 12px;
  white-space: pre-wrap;
}

.markdown-preview {
  flex: 1;
  overflow: auto;
}

.meta-list {
  border-top: 1px solid #d8dde5;
  padding-top: 10px;
  color: #596273;
}
```

Modify `apps/web/README.md` by adding:

```markdown
## Phase 1 Local Run

```powershell
npm install
npm run dev
```

The app expects the API at `http://127.0.0.1:8000` unless `VITE_API_BASE` is set.
```

- [ ] **Step 2: Install dependencies and run frontend type check/build**

Run:

```powershell
cd apps/web
npm install
npm run build
```

Expected: build succeeds and creates `dist/`.

- [ ] **Step 3: Commit**

```powershell
git add apps/web/package.json apps/web/package-lock.json apps/web/index.html apps/web/src apps/web/README.md .gitignore
git commit -m "Add web interactive skeleton"
```

## Task 6: CI And Documentation

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `docs/quality/testing.md`
- Modify: `docs/exec-plans/active/2026-04-30-phase-1-interactive-skeleton.md`

- [ ] **Step 1: Update CI for API/runtime/frontend**

Modify `.github/workflows/ci.yml` so the foundation job installs API dependencies and runs:

```yaml
      - name: Install test dependencies
        run: python -m pip install --upgrade pip pytest fastapi uvicorn httpx

      - name: Run foundation and API tests
        run: python -m pytest packages/contracts/tests packages/workspace/tests packages/timeline/tests tools/import/tests services/api/tests agent/runtime-adapters/mock/tests -q
```

Add a frontend job:

```yaml
  web:
    name: Web build
    runs-on: ubuntu-latest

    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: npm
          cache-dependency-path: apps/web/package-lock.json

      - name: Install web dependencies
        working-directory: apps/web
        run: npm ci

      - name: Build web app
        working-directory: apps/web
        run: npm run build
```

- [ ] **Step 2: Update testing docs**

Modify `docs/quality/testing.md` by adding:

```markdown
## Phase 1 Interactive Skeleton

Run backend and runtime tests:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest packages/contracts/tests packages/workspace/tests packages/timeline/tests tools/import/tests services/api/tests agent/runtime-adapters/mock/tests -q
```

Run frontend checks:

```powershell
cd apps/web
npm install
npm run build
```
```

- [ ] **Step 3: Run full Phase 1 verification**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest packages/contracts/tests packages/workspace/tests packages/timeline/tests tools/import/tests services/api/tests agent/runtime-adapters/mock/tests -q
cd apps/web
npm run build
```

Expected: all Python tests pass and frontend build succeeds.

- [ ] **Step 4: Mark execution readiness in this plan**

Add this line near the top of this plan:

```markdown
**Execution readiness:** Phase 1 backend/runtime tests and frontend build pass locally.
```

- [ ] **Step 5: Commit**

```powershell
git add .github/workflows/ci.yml docs/quality/testing.md docs/exec-plans/active/2026-04-30-phase-1-interactive-skeleton.md
git commit -m "Add Phase 1 CI and verification docs"
```

## Final Verification

Run:

```powershell
git status --short --branch
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest packages/contracts/tests packages/workspace/tests packages/timeline/tests tools/import/tests services/api/tests agent/runtime-adapters/mock/tests -q
cd apps/web
npm run build
git status --short --branch
```

Expected:

- working tree clean except ignored local caches
- all Python tests pass
- frontend build succeeds
- no generated Python cache files or `apps/web/dist` files are tracked

## Rollback Notes

- API state is file-backed under `.local/docagent`; delete that directory to reset local product data.
- Frontend dependencies live under `apps/web/node_modules`; delete and rerun `npm install` if local dependency state becomes inconsistent.
- The mock runtime adapter is isolated under `agent/runtime-adapters/mock` and can be removed without changing shared workspace helpers.
