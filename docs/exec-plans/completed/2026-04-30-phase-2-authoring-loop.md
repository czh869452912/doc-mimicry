# Phase 2 Authoring Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build the V0.2 PRD authoring loop: import Markdown-facing inputs, inspect workspace files, approve outlines, generate drafts, revise selected passages with checkpoints, run checklist review, and export Markdown artifacts.

**Architecture:** Keep the API-first vertical slice from Phase 1, but replace pure mock behavior with a controlled local authoring loop behind the runtime adapter boundary. Backend endpoints expose workspace-backed state and actions; the web app renders only real API/workspace/timeline data.

**Tech Stack:** Python 3.11, FastAPI, pytest, local filesystem state, React + Vite + TypeScript.

**Execution readiness:** Phase 2 automated tests and frontend build pass locally.

**Post-review cleanup:** Completed in `docs/exec-plans/completed/2026-05-06-phase-2-review-cleanup.md` before Phase 3 planning.

---

## Files And Responsibilities

- `packages/contracts/docagent_contracts/models.py`: add semantic event kinds needed by Phase 2.
- `packages/contracts/tests/test_models.py`: contract tests for new event kinds and artifact values.
- `services/api/docagent_api/state.py`: list tasks/sessions by task and persist session phase metadata.
- `services/api/docagent_api/workspace_files.py`: safe workspace tree listing and text file reads.
- `services/api/docagent_api/imports.py`: task input text/file import orchestration using Markdown-only conversion helpers.
- `services/api/docagent_api/app.py`: new Phase 2 endpoints for task/session lists, inputs, workspace files, outline, loop actions, checklist, and export.
- `services/api/tests/test_phase2_api.py`: end-to-end API tests for the PRD authoring loop.
- `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py`: evolve mock adapter into controlled authoring loop operations.
- `agent/runtime-adapters/mock/tests/test_authoring_loop.py`: runtime adapter tests for context, outline, draft, revision, checklist, and export.
- `apps/web/src/api.ts`: API client methods for Phase 2 endpoints.
- `apps/web/src/types.ts`: TypeScript payloads for workspace files, imports, outline, artifacts, and timeline.
- `apps/web/src/pages/WorkbenchPage.tsx`: replace Phase 1 shell behavior with the real authoring loop UI.
- `apps/web/src/pages/ManagementPage.tsx`: keep PRD doc-type display truthful; surface conversion reports clearly.
- `apps/web/src/styles.css`: support workspace tree, file viewer, outline approval, selection revision, checklist/artifact panels.
- `docs/quality/testing.md`: add Phase 2 verification commands and demo path.

## Task 1: Contract And Timeline Vocabulary

**Files:**
- Modify: `packages/contracts/docagent_contracts/models.py`
- Modify: `packages/contracts/tests/test_models.py`

- [x] **Step 1: Write failing contract test for Phase 2 event kinds**

Add this test to `packages/contracts/tests/test_models.py`:

```python
from docagent_contracts import SemanticEventKind


def test_phase2_semantic_event_kinds_are_available() -> None:
    assert SemanticEventKind.CONVERT_INPUT.value == "convert_input"
    assert SemanticEventKind.BUILD_CONTEXT.value == "build_context"
    assert SemanticEventKind.PROPOSE_OUTLINE.value == "propose_outline"
    assert SemanticEventKind.APPROVE_OUTLINE.value == "approve_outline"
    assert SemanticEventKind.REVISE_SELECTION.value == "revise_selection"
    assert SemanticEventKind.EXPORT_MARKDOWN.value == "export_markdown"
```

- [x] **Step 2: Run test to verify it fails**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest packages/contracts/tests/test_models.py::test_phase2_semantic_event_kinds_are_available -q
```

Expected: FAIL with `AttributeError` for missing enum members.

- [x] **Step 3: Add enum values**

Modify `SemanticEventKind` in `packages/contracts/docagent_contracts/models.py`:

```python
class SemanticEventKind(str, Enum):
    USER_MESSAGE = "user_message"
    AGENT_MESSAGE = "agent_message"
    READ_SKILL = "read_skill"
    ANALYZE_EXAMPLES = "analyze_examples"
    CONVERT_INPUT = "convert_input"
    BUILD_CONTEXT = "build_context"
    EXTRACT_STYLE = "extract_style"
    EXTRACT_STRUCTURE = "extract_structure"
    GENERATE_OUTLINE = "generate_outline"
    PROPOSE_OUTLINE = "propose_outline"
    APPROVE_OUTLINE = "approve_outline"
    UPDATE_DRAFT = "update_draft"
    REVISE_SELECTION = "revise_selection"
    CREATE_CHECKPOINT = "create_checkpoint"
    RUN_CHECKLIST = "run_checklist"
    EXPORT_MARKDOWN = "export_markdown"
    EXPORT_DOCX = "export_docx"
    EXPORT_PDF = "export_pdf"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_RESOLVED = "approval_resolved"
    ERROR = "error"
```

- [x] **Step 4: Run contract tests**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest packages/contracts/tests -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add packages/contracts/docagent_contracts/models.py packages/contracts/tests/test_models.py
git commit -m "Add Phase 2 timeline vocabulary"
```

## Task 2: Workspace File Browser Helpers

**Files:**
- Create: `services/api/docagent_api/workspace_files.py`
- Test: `services/api/tests/test_workspace_files.py`

- [x] **Step 1: Write failing workspace file tests**

Create `services/api/tests/test_workspace_files.py`:

```python
from pathlib import Path

import pytest

from docagent_api.workspace_files import list_workspace_files, read_workspace_text_file


def test_lists_workspace_files_by_group(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "context").mkdir(parents=True)
    (workspace / "draft").mkdir()
    (workspace / "brief.md").write_text("Brief\n", encoding="utf-8")
    (workspace / "context" / "user_intent.md").write_text("Intent\n", encoding="utf-8")
    (workspace / "draft" / "draft.md").write_text("Draft\n", encoding="utf-8")

    files = list_workspace_files(workspace)

    assert files == [
        {"path": "brief.md", "group": "brief", "kind": "markdown"},
        {"path": "context/user_intent.md", "group": "context", "kind": "markdown"},
        {"path": "draft/draft.md", "group": "draft", "kind": "markdown"},
    ]


def test_reads_text_file_inside_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "draft").mkdir(parents=True)
    (workspace / "draft" / "draft.md").write_text("# Draft\n", encoding="utf-8")

    assert read_workspace_text_file(workspace, "draft/draft.md") == "# Draft\n"


def test_rejects_path_traversal(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(ValueError, match="outside workspace"):
        read_workspace_text_file(workspace, "../secret.md")
```

- [x] **Step 2: Run test to verify it fails**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest services/api/tests/test_workspace_files.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'docagent_api.workspace_files'`.

- [x] **Step 3: Implement workspace file helpers**

Create `services/api/docagent_api/workspace_files.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any


TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".json", ".yaml", ".yml"}


def list_workspace_files(workspace_root: Path) -> list[dict[str, Any]]:
    if not workspace_root.exists():
        return []
    files: list[dict[str, Any]] = []
    for path in sorted(workspace_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(workspace_root).as_posix()
        files.append({
            "path": relative,
            "group": _group_for(relative),
            "kind": _kind_for(path),
        })
    return files


def read_workspace_text_file(workspace_root: Path, relative_path: str) -> str:
    path = _resolve_inside(workspace_root, relative_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(relative_path)
    if path.suffix.lower() not in TEXT_SUFFIXES:
        raise ValueError("not a text file")
    return path.read_text(encoding="utf-8")


def _resolve_inside(workspace_root: Path, relative_path: str) -> Path:
    root = workspace_root.resolve()
    path = (workspace_root / relative_path).resolve()
    if root != path and root not in path.parents:
        raise ValueError("path is outside workspace")
    return path


def _group_for(relative_path: str) -> str:
    if relative_path == "brief.md":
        return "brief"
    return relative_path.split("/", 1)[0]


def _kind_for(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown"}:
        return "markdown"
    if suffix in {".txt", ".json", ".yaml", ".yml"}:
        return "text"
    return "binary"
```

- [x] **Step 4: Run workspace file tests**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest services/api/tests/test_workspace_files.py -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add services/api/docagent_api/workspace_files.py services/api/tests/test_workspace_files.py
git commit -m "Add workspace file browser helpers"
```

## Task 3: Input Import API Helpers

**Files:**
- Create: `services/api/docagent_api/imports.py`
- Test: `services/api/tests/test_imports.py`

- [x] **Step 1: Write failing import tests**

Create `services/api/tests/test_imports.py`:

```python
from pathlib import Path

from docagent_api.imports import import_text_input


def test_import_text_input_writes_original_markdown_and_report(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"

    result = import_text_input(
        workspace_root=workspace,
        name="notes.txt",
        content="User research notes",
        created_at="2026-04-30T00:00:00Z",
    )

    assert result["status"] == "converted"
    assert result["source_path"] == "inputs/original/notes.txt"
    assert result["markdown_path"] == "inputs/markdown/notes.md"
    assert (workspace / "inputs" / "original" / "notes.txt").read_text(encoding="utf-8") == "User research notes\n"
    assert (workspace / "inputs" / "markdown" / "notes.md").read_text(encoding="utf-8") == "User research notes\n"
    assert (workspace / "inputs" / "reports" / "notes.json").exists()
```

- [x] **Step 2: Run test to verify it fails**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest services/api/tests/test_imports.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'docagent_api.imports'`.

- [x] **Step 3: Implement text input import**

Create `services/api/docagent_api/imports.py`:

```python
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def import_text_input(
    workspace_root: Path,
    name: str,
    content: str,
    created_at: str,
) -> dict[str, Any]:
    stem = _safe_stem(name)
    original_path = workspace_root / "inputs" / "original" / f"{stem}.txt"
    markdown_path = workspace_root / "inputs" / "markdown" / f"{stem}.md"
    report_path = workspace_root / "inputs" / "reports" / f"{stem}.json"
    for path in [original_path.parent, markdown_path.parent, report_path.parent]:
        path.mkdir(parents=True, exist_ok=True)
    text = content if content.endswith("\n") else f"{content}\n"
    original_path.write_text(text, encoding="utf-8")
    markdown_path.write_text(text, encoding="utf-8")
    report = {
        "source_path": original_path.relative_to(workspace_root).as_posix(),
        "markdown_path": markdown_path.relative_to(workspace_root).as_posix(),
        "asset_dir": None,
        "engine": "manual",
        "status": "succeeded",
        "warnings": [],
        "features_detected": {
            "tables": 0,
            "images": 0,
            "formulas": 0,
            "footnotes": 0,
            "pages": None,
        },
        "created_at": created_at,
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "id": f"input-{stem}",
        "status": "converted",
        "source_path": report["source_path"],
        "markdown_path": report["markdown_path"],
        "conversion_report_path": report_path.relative_to(workspace_root).as_posix(),
        "original_filename": name,
        "created_at": created_at,
    }


def _safe_stem(name: str) -> str:
    raw_stem = Path(name).stem or "input"
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", raw_stem).strip("-").lower()
    return stem or "input"
```

- [x] **Step 4: Run import tests**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest services/api/tests/test_imports.py -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add services/api/docagent_api/imports.py services/api/tests/test_imports.py
git commit -m "Add task input import helper"
```

## Task 4: Controlled Authoring Loop Adapter

**Files:**
- Modify: `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py`
- Test: `agent/runtime-adapters/mock/tests/test_authoring_loop.py`

- [x] **Step 1: Write failing authoring loop tests**

Create `agent/runtime-adapters/mock/tests/test_authoring_loop.py`:

```python
from pathlib import Path

from docagent_mock_runtime.adapter import MockRuntimeAdapter


def test_build_context_and_propose_outline(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "inputs" / "markdown").mkdir(parents=True)
    (workspace / "brief.md").write_text("Build a PRD for onboarding analytics\n", encoding="utf-8")
    (workspace / "inputs" / "markdown" / "notes.md").write_text("Users need funnel visibility.\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()
    events = adapter.build_context_and_outline("task-001", "session-001", workspace)

    assert (workspace / "context" / "user_intent.md").exists()
    assert (workspace / "context" / "doc_map.md").exists()
    assert (workspace / "draft" / "outline.md").exists()
    assert [event.kind.value for event in events] == [
        "read_skill",
        "analyze_examples",
        "build_context",
        "extract_style",
        "extract_structure",
        "propose_outline",
        "approval_requested",
    ]


def test_approve_outline_generates_draft(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "draft").mkdir(parents=True)
    (workspace / "brief.md").write_text("Build a PRD for onboarding analytics\n", encoding="utf-8")
    (workspace / "draft" / "outline.md").write_text("# Outline\n\n1. Problem\n2. Goals\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()
    events = adapter.approve_outline_and_draft("task-001", "session-001", workspace, "# Outline\n\n1. Problem\n2. Goals\n")

    assert "# PRD Draft" in (workspace / "draft" / "draft.md").read_text(encoding="utf-8")
    assert [event.kind.value for event in events] == ["approve_outline", "update_draft"]


def test_revise_selection_checkpoints_and_replaces_text(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "draft").mkdir(parents=True)
    (workspace / "draft" / "draft.md").write_text("# PRD Draft\n\nOld passage\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()
    events = adapter.revise_selection(
        "task-001",
        "session-001",
        workspace,
        selected_text="Old passage",
        instruction="Make it sharper",
    )

    draft = (workspace / "draft" / "draft.md").read_text(encoding="utf-8")
    assert "Old passage" not in draft
    assert "Make it sharper" in draft
    assert (workspace / "versions" / "v001.md").exists()
    assert [event.kind.value for event in events] == ["create_checkpoint", "revise_selection"]


def test_run_checklist_and_export_markdown(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "draft").mkdir(parents=True)
    (workspace / "draft" / "draft.md").write_text("# PRD Draft\n\n## Goals\n\n- Improve activation\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()
    checklist_events = adapter.run_checklist("task-001", "session-001", workspace)
    export_events = adapter.export_markdown("task-001", "session-001", workspace)

    assert (workspace / "reviews" / "checklist_result.md").exists()
    assert (workspace / "artifacts" / "prd-draft.md").exists()
    assert [event.kind.value for event in checklist_events] == ["run_checklist"]
    assert [event.kind.value for event in export_events] == ["export_markdown"]
```

- [x] **Step 2: Run test to verify it fails**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest agent/runtime-adapters/mock/tests/test_authoring_loop.py -q
```

Expected: FAIL with missing `build_context_and_outline` method.

- [x] **Step 3: Implement controlled loop methods**

Modify `MockRuntimeAdapter` in `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py` by adding these methods:

```python
    def build_context_and_outline(
        self,
        task_id: str,
        session_id: str,
        workspace_root: Path,
    ) -> list[SemanticTimelineEvent]:
        (workspace_root / "context").mkdir(parents=True, exist_ok=True)
        (workspace_root / "draft").mkdir(parents=True, exist_ok=True)
        brief = _read_text(workspace_root / "brief.md").strip()
        input_notes = _read_markdown_inputs(workspace_root)
        (workspace_root / "context" / "user_intent.md").write_text(
            f"# User Intent\n\n{brief}\n",
            encoding="utf-8",
        )
        (workspace_root / "context" / "doc_map.md").write_text(
            "# Document Map\n\n- brief.md: user intent\n- inputs/markdown: source materials\n",
            encoding="utf-8",
        )
        (workspace_root / "context" / "style_notes.md").write_text(
            "# Style Notes\n\nUse concise PRD prose, explicit bullets, and decision-ready sections.\n",
            encoding="utf-8",
        )
        (workspace_root / "context" / "structure_notes.md").write_text(
            "# Structure Notes\n\nProblem, Goals, Users, Requirements, Risks, Open Questions.\n",
            encoding="utf-8",
        )
        (workspace_root / "draft" / "outline.md").write_text(
            "# Outline\n\n"
            "1. Problem\n"
            "2. Goals\n"
            "3. Users\n"
            "4. Requirements\n"
            "5. Risks\n"
            "6. Open Questions\n\n"
            f"## Input Signals\n\n{input_notes or '- No additional inputs yet.'}\n",
            encoding="utf-8",
        )
        return [
            _event(task_id, session_id, "skill", TimelineActor.AGENT, SemanticEventKind.READ_SKILL, "Read PRD skill", ["doc-types/prd/SKILL.md"]),
            _event(task_id, session_id, "examples", TimelineActor.AGENT, SemanticEventKind.ANALYZE_EXAMPLES, "Analyze PRD examples", ["doc-types/prd/examples/markdown"]),
            _event(task_id, session_id, "context", TimelineActor.AGENT, SemanticEventKind.BUILD_CONTEXT, "Build context files", ["context/user_intent.md", "context/doc_map.md"]),
            _event(task_id, session_id, "style", TimelineActor.AGENT, SemanticEventKind.EXTRACT_STYLE, "Extract style notes", ["context/style_notes.md"]),
            _event(task_id, session_id, "structure", TimelineActor.AGENT, SemanticEventKind.EXTRACT_STRUCTURE, "Extract structure notes", ["context/structure_notes.md"]),
            _event(task_id, session_id, "outline", TimelineActor.AGENT, SemanticEventKind.PROPOSE_OUTLINE, "Propose outline", ["draft/outline.md"]),
            _event(task_id, session_id, "approval", TimelineActor.SYSTEM, SemanticEventKind.APPROVAL_REQUESTED, "Await outline approval", ["draft/outline.md"]),
        ]

    def approve_outline_and_draft(
        self,
        task_id: str,
        session_id: str,
        workspace_root: Path,
        outline_markdown: str,
    ) -> list[SemanticTimelineEvent]:
        (workspace_root / "draft").mkdir(parents=True, exist_ok=True)
        outline_text = outline_markdown if outline_markdown.endswith("\n") else f"{outline_markdown}\n"
        (workspace_root / "draft" / "outline.md").write_text(outline_text, encoding="utf-8")
        brief = _read_text(workspace_root / "brief.md").strip()
        (workspace_root / "draft" / "draft.md").write_text(
            "# PRD Draft\n\n"
            "## Problem\n\n"
            f"{brief or 'Clarify the product problem.'}\n\n"
            "## Goals\n\n- Define the desired product outcome.\n\n"
            "## Users\n\n- Identify primary users and reviewers.\n\n"
            "## Requirements\n\n- Describe the first usable workflow.\n\n"
            "## Risks\n\n- Validate assumptions before launch.\n",
            encoding="utf-8",
        )
        return [
            _event(task_id, session_id, "outline-approved", TimelineActor.USER, SemanticEventKind.APPROVE_OUTLINE, "Approve outline", ["draft/outline.md"]),
            _event(task_id, session_id, "draft", TimelineActor.AGENT, SemanticEventKind.UPDATE_DRAFT, "Generate draft", ["draft/draft.md"]),
        ]

    def revise_selection(
        self,
        task_id: str,
        session_id: str,
        workspace_root: Path,
        selected_text: str,
        instruction: str,
    ) -> list[SemanticTimelineEvent]:
        checkpoint = checkpoint_draft(workspace_root, summary=f"Before selection revision: {instruction}")
        draft_path = workspace_root / "draft" / "draft.md"
        current = _read_text(draft_path)
        replacement = f"{selected_text} ({instruction})"
        draft_path.write_text(current.replace(selected_text, replacement, 1), encoding="utf-8")
        return [
            _event(task_id, session_id, "checkpoint", TimelineActor.SYSTEM, SemanticEventKind.CREATE_CHECKPOINT, "Create checkpoint", [checkpoint.version_path]),
            _event(task_id, session_id, "selection", TimelineActor.AGENT, SemanticEventKind.REVISE_SELECTION, "Revise selected passage", ["draft/draft.md"]),
        ]

    def run_checklist(
        self,
        task_id: str,
        session_id: str,
        workspace_root: Path,
    ) -> list[SemanticTimelineEvent]:
        (workspace_root / "reviews").mkdir(parents=True, exist_ok=True)
        draft = _read_text(workspace_root / "draft" / "draft.md")
        result = "# Checklist Result\n\n- [x] Has draft content\n- [x] Has PRD heading\n"
        if "## Risks" not in draft:
            result += "- [ ] Includes risks section\n"
        else:
            result += "- [x] Includes risks section\n"
        (workspace_root / "reviews" / "checklist_result.md").write_text(result, encoding="utf-8")
        return [_event(task_id, session_id, "checklist", TimelineActor.AGENT, SemanticEventKind.RUN_CHECKLIST, "Run checklist", ["reviews/checklist_result.md"])]

    def export_markdown(
        self,
        task_id: str,
        session_id: str,
        workspace_root: Path,
    ) -> list[SemanticTimelineEvent]:
        (workspace_root / "artifacts").mkdir(parents=True, exist_ok=True)
        artifact_path = workspace_root / "artifacts" / "prd-draft.md"
        artifact_path.write_text(_read_text(workspace_root / "draft" / "draft.md"), encoding="utf-8")
        return [_event(task_id, session_id, "export-md", TimelineActor.SYSTEM, SemanticEventKind.EXPORT_MARKDOWN, "Export Markdown artifact", ["artifacts/prd-draft.md"])]
```

Also add this helper at module level:

```python
def _read_markdown_inputs(workspace_root: Path) -> str:
    markdown_dir = workspace_root / "inputs" / "markdown"
    if not markdown_dir.exists():
        return ""
    chunks = []
    for path in sorted(markdown_dir.glob("*.md")):
        chunks.append(f"### {path.name}\n\n{path.read_text(encoding='utf-8').strip()}")
    return "\n\n".join(chunks)
```

- [x] **Step 4: Run adapter tests**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest agent/runtime-adapters/mock/tests -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py agent/runtime-adapters/mock/tests/test_authoring_loop.py
git commit -m "Add controlled PRD authoring loop"
```

## Task 5: Phase 2 API Endpoints

**Files:**
- Modify: `services/api/docagent_api/app.py`
- Test: `services/api/tests/test_phase2_api.py`

- [x] **Step 1: Write failing Phase 2 API test**

Create `services/api/tests/test_phase2_api.py`:

```python
from pathlib import Path

from fastapi.testclient import TestClient

from docagent_api.app import create_app


def test_phase2_prd_authoring_loop_api(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))

    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build onboarding analytics"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    import_response = client.post(
        f"/tasks/{task['id']}/inputs/text",
        json={"name": "research.txt", "content": "Users need funnel visibility."},
    )
    assert import_response.status_code == 200
    assert import_response.json()["markdown_path"] == "inputs/markdown/research.md"

    start_response = client.post(f"/sessions/{session['id']}/loop/start")
    assert start_response.status_code == 200
    assert start_response.json()["next_state"] == "await_outline_approval"

    workspace = client.get(f"/tasks/{task['id']}/workspace").json()
    assert "draft/outline.md" in [file["path"] for file in workspace["files"]]

    outline = client.get(f"/tasks/{task['id']}/workspace/files", params={"path": "draft/outline.md"}).json()
    assert "# Outline" in outline["content"]

    approve_response = client.post(
        f"/sessions/{session['id']}/outline/approve",
        json={"outline_markdown": outline["content"]},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["next_state"] == "draft_ready"

    draft = client.get(f"/tasks/{task['id']}/draft").json()["markdown"]
    assert "# PRD Draft" in draft

    revise_response = client.post(
        f"/sessions/{session['id']}/revision/selection",
        json={"selected_text": "Build onboarding analytics", "instruction": "Make the problem statement sharper"},
    )
    assert revise_response.status_code == 200

    workspace_after_revision = client.get(f"/tasks/{task['id']}/workspace").json()
    assert any(file["path"].startswith("versions/") for file in workspace_after_revision["files"])

    checklist_response = client.post(f"/sessions/{session['id']}/checklist/run")
    assert checklist_response.status_code == 200
    assert "reviews/checklist_result.md" in checklist_response.json()["paths"]

    export_response = client.post(f"/sessions/{session['id']}/artifacts/export-markdown")
    assert export_response.status_code == 200
    assert export_response.json()["artifact_path"] == "artifacts/prd-draft.md"

    timeline = client.get(f"/sessions/{session['id']}/timeline").json()
    assert "convert_input" in [event["kind"] for event in timeline]
    assert "propose_outline" in [event["kind"] for event in timeline]
    assert "approve_outline" in [event["kind"] for event in timeline]
    assert "revise_selection" in [event["kind"] for event in timeline]
    assert "run_checklist" in [event["kind"] for event in timeline]
    assert "export_markdown" in [event["kind"] for event in timeline]
```

- [x] **Step 2: Run test to verify it fails**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest services/api/tests/test_phase2_api.py -q
```

Expected: FAIL because `/tasks/{task_id}/inputs/text` is not implemented.

- [x] **Step 3: Add request models and endpoints**

Modify `services/api/docagent_api/app.py`:

```python
from docagent_api.imports import import_text_input
from docagent_api.workspace_files import list_workspace_files, read_workspace_text_file
from docagent_contracts import SemanticEventKind, SemanticTimelineEvent, TimelineActor, TimelineStatus
```

Add request models:

```python
class ImportTextRequest(BaseModel):
    name: str
    content: str


class ApproveOutlineRequest(BaseModel):
    outline_markdown: str


class ReviseSelectionRequest(BaseModel):
    selected_text: str
    instruction: str
```

Update `get_workspace` so `files` comes from `list_workspace_files`.

Add endpoints:

```python
    @app.get("/tasks")
    def list_tasks() -> list[dict[str, Any]]:
        return state.list_tasks()

    @app.get("/tasks/{task_id}/sessions")
    def list_task_sessions(task_id: str) -> list[dict[str, Any]]:
        _require_task(state, task_id)
        return [session for session in state.list_sessions() if session["task_id"] == task_id]

    @app.post("/tasks/{task_id}/inputs/text")
    def add_text_input(task_id: str, request: ImportTextRequest) -> dict[str, Any]:
        task = _require_task(state, task_id)
        result = import_text_input(Path(task["workspace_root"]), request.name, request.content, "2026-04-30T00:00:00Z")
        sessions = [session for session in state.list_sessions() if session["task_id"] == task_id]
        if sessions:
            event = _manual_event(task_id, sessions[0]["id"], "convert-input", TimelineActor.SYSTEM, SemanticEventKind.CONVERT_INPUT, "Convert input to Markdown", [result["markdown_path"]])
            state.append_timeline_event(sessions[0]["id"], asdict(event))
            result["event"] = asdict(event)
        return result

    @app.get("/tasks/{task_id}/workspace/files")
    def get_workspace_file(task_id: str, path: str) -> dict[str, str]:
        task = _require_task(state, task_id)
        return {"path": path, "content": read_workspace_text_file(Path(task["workspace_root"]), path)}

    @app.post("/sessions/{session_id}/loop/start")
    def start_loop(session_id: str) -> dict[str, Any]:
        session = _require_session(state, session_id)
        task = _require_task(state, session["task_id"])
        events = adapter.build_context_and_outline(task["id"], session_id, Path(task["workspace_root"]))
        _append_events(state, session_id, events)
        session["status"] = "await_outline_approval"
        state.save_session(session)
        return {"session_id": session_id, "next_state": "await_outline_approval", "event_count": len(events)}

    @app.post("/sessions/{session_id}/outline/approve")
    def approve_outline(session_id: str, request: ApproveOutlineRequest) -> dict[str, Any]:
        session = _require_session(state, session_id)
        task = _require_task(state, session["task_id"])
        events = adapter.approve_outline_and_draft(task["id"], session_id, Path(task["workspace_root"]), request.outline_markdown)
        _append_events(state, session_id, events)
        session["status"] = "draft_ready"
        state.save_session(session)
        return {"session_id": session_id, "next_state": "draft_ready", "event_count": len(events)}

    @app.post("/sessions/{session_id}/revision/selection")
    def revise_selection(session_id: str, request: ReviseSelectionRequest) -> dict[str, Any]:
        session = _require_session(state, session_id)
        task = _require_task(state, session["task_id"])
        events = adapter.revise_selection(task["id"], session_id, Path(task["workspace_root"]), request.selected_text, request.instruction)
        _append_events(state, session_id, events)
        return {"session_id": session_id, "paths": [path for event in events for path in event.paths]}

    @app.post("/sessions/{session_id}/checklist/run")
    def run_checklist(session_id: str) -> dict[str, Any]:
        session = _require_session(state, session_id)
        task = _require_task(state, session["task_id"])
        events = adapter.run_checklist(task["id"], session_id, Path(task["workspace_root"]))
        _append_events(state, session_id, events)
        return {"session_id": session_id, "paths": [path for event in events for path in event.paths]}

    @app.post("/sessions/{session_id}/artifacts/export-markdown")
    def export_markdown(session_id: str) -> dict[str, Any]:
        session = _require_session(state, session_id)
        task = _require_task(state, session["task_id"])
        events = adapter.export_markdown(task["id"], session_id, Path(task["workspace_root"]))
        _append_events(state, session_id, events)
        return {"session_id": session_id, "artifact_path": "artifacts/prd-draft.md"}
```

Add helpers:

```python
def _require_session(state: DocAgentState, session_id: str) -> dict[str, Any]:
    session = state.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def _append_events(state: DocAgentState, session_id: str, events: list[SemanticTimelineEvent]) -> None:
    for event in events:
        state.append_timeline_event(session_id, asdict(event))


def _manual_event(
    task_id: str,
    session_id: str,
    suffix: str,
    actor: TimelineActor,
    kind: SemanticEventKind,
    summary: str,
    paths: list[str],
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
        status=TimelineStatus.SUCCEEDED,
        created_at="2026-04-30T00:00:00Z",
    )
```

The input conversion endpoint is task-scoped. When at least one task session exists, append the `convert_input` event to the first session for that task so the Phase 2 demo timeline remains complete. The UI must create a session before importing input material.

- [x] **Step 4: Run Phase 2 API test**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest services/api/tests/test_phase2_api.py -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add services/api/docagent_api/app.py services/api/tests/test_phase2_api.py
git commit -m "Add Phase 2 authoring API"
```

## Task 6: Web API Client And Types

**Files:**
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/api.ts`

- [x] **Step 1: Update TypeScript types**

Modify `apps/web/src/types.ts`:

```typescript
export interface WorkspaceFile {
  path: string;
  group: string;
  kind: string;
}

export interface WorkspaceTree {
  task_id: string;
  root: string;
  files: WorkspaceFile[];
}

export interface WorkspaceFileContent {
  path: string;
  content: string;
}

export interface ImportedInput {
  id: string;
  status: string;
  source_path: string;
  markdown_path: string;
  conversion_report_path: string;
  original_filename: string;
}

export interface LoopActionResult {
  session_id: string;
  next_state?: string;
  event_count?: number;
  paths?: string[];
  artifact_path?: string;
}
```

- [x] **Step 2: Update API client**

Modify `apps/web/src/api.ts` by importing the new types and adding:

```typescript
  listTasks: () => request<TaskRecord[]>("/tasks"),
  listTaskSessions: (taskId: string) => request<SessionRecord[]>(`/tasks/${taskId}/sessions`),
  getWorkspace: (taskId: string) => request<WorkspaceTree>(`/tasks/${taskId}/workspace`),
  getWorkspaceFile: (taskId: string, path: string) =>
    request<WorkspaceFileContent>(`/tasks/${taskId}/workspace/files?path=${encodeURIComponent(path)}`),
  importTextInput: (taskId: string, name: string, content: string) =>
    request<ImportedInput>(`/tasks/${taskId}/inputs/text`, {
      method: "POST",
      body: JSON.stringify({ name, content }),
    }),
  startLoop: (sessionId: string) =>
    request<LoopActionResult>(`/sessions/${sessionId}/loop/start`, { method: "POST" }),
  approveOutline: (sessionId: string, outline_markdown: string) =>
    request<LoopActionResult>(`/sessions/${sessionId}/outline/approve`, {
      method: "POST",
      body: JSON.stringify({ outline_markdown }),
    }),
  reviseSelection: (sessionId: string, selected_text: string, instruction: string) =>
    request<LoopActionResult>(`/sessions/${sessionId}/revision/selection`, {
      method: "POST",
      body: JSON.stringify({ selected_text, instruction }),
    }),
  runChecklist: (sessionId: string) =>
    request<LoopActionResult>(`/sessions/${sessionId}/checklist/run`, { method: "POST" }),
  exportMarkdown: (sessionId: string) =>
    request<LoopActionResult>(`/sessions/${sessionId}/artifacts/export-markdown`, { method: "POST" }),
```

- [x] **Step 3: Run frontend type check**

Run:

```powershell
cd apps/web
npm run test
```

Expected: PASS.

- [x] **Step 4: Commit**

```powershell
git add apps/web/src/types.ts apps/web/src/api.ts
git commit -m "Add Phase 2 web API client"
```

## Task 7: Workbench UI For Real Authoring Loop

**Files:**
- Modify: `apps/web/src/pages/WorkbenchPage.tsx`
- Modify: `apps/web/src/styles.css`

- [x] **Step 1: Replace Phase 1 workbench shell with real loop UI**

Modify `apps/web/src/pages/WorkbenchPage.tsx` so it supports:

- task creation and recovery from `api.listTasks`;
- session creation and recovery from `api.listTaskSessions`;
- text input import;
- workspace tree refresh and file opening;
- start loop;
- outline editing and approval;
- draft editing and manual save;
- selected text revision using textarea selection;
- checklist run;
- Markdown artifact export;
- timeline refresh after each action.

Use these state variables:

```typescript
const [tasks, setTasks] = useState<TaskRecord[]>([]);
const [workspace, setWorkspace] = useState<WorkspaceTree | null>(null);
const [openFile, setOpenFile] = useState<WorkspaceFileContent | null>(null);
const [inputName, setInputName] = useState("research.txt");
const [inputContent, setInputContent] = useState("Users need clearer onboarding analytics.");
const [outline, setOutline] = useState("");
const [revisionInstruction, setRevisionInstruction] = useState("Make this passage more specific.");
const [selectedText, setSelectedText] = useState("");
const [status, setStatus] = useState("");
```

Implement helper functions:

```typescript
async function refreshTaskState(nextTask = task, nextSession = session) {
  if (!nextTask) return;
  setWorkspace(await api.getWorkspace(nextTask.id));
  setDraft((await api.getDraft(nextTask.id)).markdown);
  const outlineFile = await api.getWorkspaceFile(nextTask.id, "draft/outline.md").catch(() => null);
  setOutline(outlineFile?.content ?? "");
  if (nextSession) {
    setTimeline(await api.getTimeline(nextSession.id));
  }
}

function captureSelection(event: React.SyntheticEvent<HTMLTextAreaElement>) {
  const target = event.currentTarget;
  setSelectedText(target.value.slice(target.selectionStart, target.selectionEnd));
}
```

The rendered layout should keep the three-column shape:

- left: doc type, brief, task/session list, import text, workspace tree;
- center: timeline, loop action buttons, message composer;
- right: file viewer, outline editor, draft editor, selected revision, checklist/export actions.

Do not add controls that do not call real API methods.

- [x] **Step 2: Update CSS for Phase 2 workbench**

Modify `apps/web/src/styles.css` to add classes:

```css
.stack { display: flex; flex-direction: column; gap: 10px; }
.row { display: flex; gap: 8px; align-items: center; }
.file-list { display: flex; flex-direction: column; gap: 4px; }
.file-list button { justify-content: flex-start; width: 100%; }
.action-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.status-line { min-height: 22px; color: #4169a8; }
.split-preview { display: grid; grid-template-rows: minmax(160px, 1fr) minmax(160px, 1fr); gap: 10px; min-height: 0; }
```

- [x] **Step 3: Run frontend build**

Run:

```powershell
cd apps/web
npm run build
```

Expected: PASS.

- [x] **Step 4: Commit**

```powershell
git add apps/web/src/pages/WorkbenchPage.tsx apps/web/src/styles.css
git commit -m "Build Phase 2 authoring workbench"
```

## Task 8: Management Resource Truthfulness

**Files:**
- Modify: `services/api/docagent_api/doctypes.py`
- Modify: `services/api/tests/test_doctypes_and_drafts.py`
- Modify: `apps/web/src/pages/ManagementPage.tsx`

- [x] **Step 1: Add report-aware doctype test**

Add to `services/api/tests/test_doctypes_and_drafts.py`:

```python
def test_doc_type_detail_groups_markdown_and_reports() -> None:
    detail = get_doc_type(Path("doc-types"), "prd")

    assert detail is not None
    assert "examples" in detail["resource_groups"]
    assert "specs" in detail["resource_groups"]
    assert "checklists" in detail["resource_groups"]
    assert "export-references" in detail["resource_groups"]
```

- [x] **Step 2: Run doctype tests**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest services/api/tests/test_doctypes_and_drafts.py -q
```

Expected: PASS or fail if current grouping does not expose expected groups.

- [x] **Step 3: Update management page to show resource groups as real data**

Modify `apps/web/src/pages/ManagementPage.tsx`:

- keep doc type selection;
- display each `resource_groups` entry in a compact list;
- keep `SKILL.md` preview;
- show a non-interactive note that Skill Creator is out of scope for Phase 2 rather than pretending it is usable.

- [x] **Step 4: Run frontend build**

Run:

```powershell
cd apps/web
npm run build
```

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add services/api/docagent_api/doctypes.py services/api/tests/test_doctypes_and_drafts.py apps/web/src/pages/ManagementPage.tsx
git commit -m "Make PRD management resources truthful"
```

## Task 9: Phase 2 Documentation And CI

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `docs/quality/testing.md`
- Modify: `docs/exec-plans/active/2026-04-30-phase-2-authoring-loop.md`

- [x] **Step 1: Update CI Python test command**

Modify `.github/workflows/ci.yml` so the Python job runs:

```yaml
python -m pytest packages/contracts/tests packages/workspace/tests packages/timeline/tests tools/import/tests services/api/tests agent/runtime-adapters/mock/tests tests -q
```

- [x] **Step 2: Update testing docs**

Add to `docs/quality/testing.md`:

```markdown
## Phase 2 Authoring Loop

Run backend/runtime tests:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest packages/contracts/tests packages/workspace/tests packages/timeline/tests tools/import/tests services/api/tests agent/runtime-adapters/mock/tests tests -q
```

Run frontend build:

```powershell
cd apps/web
npm run build
```

Manual demo path:

1. `.\start-dev.cmd`
2. create a PRD task
3. add text input
4. start loop
5. approve outline
6. revise selected draft passage
7. run checklist
8. export Markdown artifact
```

- [x] **Step 3: Mark plan execution readiness**

Add near the top of this plan after Tech Stack:

```markdown
**Execution readiness:** Phase 2 automated tests and frontend build pass locally.
```

- [x] **Step 4: Run full verification**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest packages/contracts/tests packages/workspace/tests packages/timeline/tests tools/import/tests services/api/tests agent/runtime-adapters/mock/tests tests -q
cd apps/web
npm run build
```

Expected: all tests pass and web build succeeds.

- [x] **Step 5: Commit**

```powershell
git add .github/workflows/ci.yml docs/quality/testing.md docs/exec-plans/active/2026-04-30-phase-2-authoring-loop.md
git commit -m "Add Phase 2 verification docs"
```

## Final Verification

Run:

```powershell
git status --short --branch
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest packages/contracts/tests packages/workspace/tests packages/timeline/tests tools/import/tests services/api/tests agent/runtime-adapters/mock/tests tests -q
cd apps/web
npm run build
git status --short --branch
git ls-files | Select-String -Pattern '__pycache__|\.pyc$|\.pytest_cache|apps/web/dist|node_modules|\.local'
```

Expected:

- all Python tests pass;
- frontend build succeeds;
- working tree is clean;
- no generated caches, local state, `dist`, or `node_modules` are tracked.

## Rollback Notes

- Local product state remains under `.local/docagent`.
- Local startup logs and virtual environment remain under `.local/dev`.
- Phase 2 authoring loop changes are isolated behind the existing runtime adapter boundary.
- If UI work needs to be backed out, the Phase 2 API tests should still preserve backend loop behavior.
