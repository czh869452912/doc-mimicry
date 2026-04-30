# Phase 0 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the minimum contract, workspace, import, checkpoint, and timeline foundation needed before UI or agent runtime integration.

**Architecture:** Implement small, testable Python packages and scripts around the existing Markdown-only workspace contract. The first slice avoids React/FastAPI/OpenHands integration and instead creates reliable file-system primitives, JSON-compatible schemas, and semantic event mapping that later layers can reuse.

**Tech Stack:** Python 3.11+, pytest, standard-library dataclasses/enums, Markdown files, JSON conversion reports.

---

## Scope

This plan implements the Phase 0 foundation layer:

- Shared Python contract models matching `packages/contracts/schemas.md`.
- Workspace creation and validation helpers.
- Checkpoint helper and CLI.
- Import conversion helper with direct Markdown/text normalization and explicit unsupported-format failure reports.
- Timeline semantic mapper for workspace path and command events.
- GitHub Actions CI for foundation tests.
- Tests for all foundation behavior.

## Non-Goals

- React UI.
- FastAPI service.
- OpenHands runtime adapter.
- Real DOCX/PDF/PPTX parsing via Docling/MarkItDown/MinerU/Marker.
- Pandoc/LibreOffice DOCX export.
- Database schema.

## Files And Modules

Create:

- `pyproject.toml`: minimal Python project metadata and pytest config.
- `packages/contracts/docagent_contracts/__init__.py`: exports contract models.
- `packages/contracts/docagent_contracts/models.py`: shared enums and dataclasses.
- `packages/contracts/tests/test_models.py`: contract model tests.
- `packages/workspace/docagent_workspace/__init__.py`: exports workspace helpers.
- `packages/workspace/docagent_workspace/layout.py`: workspace path constants and creation helpers.
- `packages/workspace/docagent_workspace/validation.py`: workspace validation.
- `packages/workspace/docagent_workspace/checkpoint.py`: draft version creation.
- `packages/workspace/tests/test_layout.py`: workspace creation tests.
- `packages/workspace/tests/test_validation.py`: validation tests.
- `packages/workspace/tests/test_checkpoint.py`: checkpoint tests.
- `tools/workspace/validate_workspace.py`: CLI wrapper for validation.
- `tools/workspace/checkpoint.py`: CLI wrapper for checkpointing.
- `tools/import/convert_to_markdown.py`: CLI for direct Markdown/text import and unsupported report creation.
- `tools/import/inspect_conversion.py`: CLI to print conversion report summaries.
- `tools/import/tests/test_convert_to_markdown.py`: import CLI tests.
- `packages/timeline/docagent_timeline/__init__.py`: exports timeline mapper.
- `packages/timeline/docagent_timeline/mapper.py`: semantic event mapping.
- `packages/timeline/tests/test_mapper.py`: timeline mapper tests.
- `.github/workflows/ci.yml`: extend the existing baseline workflow to run foundation tests on push and pull request.

Modify:

- `packages/contracts/README.md`: document Python model location.
- `packages/workspace/README.md`: document helper modules and commands.
- `packages/timeline/README.md`: document mapper input/output.
- `tools/import/README.md`: document Phase 0 supported formats.
- `tools/workspace/README.md`: document CLI usage.
- `docs/quality/testing.md`: add Phase 0 pytest and CI commands.

## Verification Commands

Run after implementation:

```powershell
python -m pytest packages/contracts/tests packages/workspace/tests packages/timeline/tests tools/import/tests -q
```

Expected:

```text
all tests pass
```

CI check:

```powershell
Get-Content .github/workflows/ci.yml
```

Expected: workflow runs on `push` and `pull_request`. After Task 6, it also installs `pytest` and runs the foundation pytest command.

Manual smoke check:

```powershell
$root = Join-Path $env:TEMP "docagent-plan-smoke"
Remove-Item -Recurse -Force $root -ErrorAction SilentlyContinue
python tools/workspace/validate_workspace.py --workspace $root
```

Expected before creation:

```text
invalid
```

Then create a workspace through the helper in tests or a temporary Python snippet and validate again.

## Rollback Or Recovery

- If package layout becomes too heavy, keep the CLI scripts and move shared logic back into `tools/` only. Do not proceed to UI/API until workspace validation and checkpoint behavior are reliable.
- If Pydantic is not available and dependency setup is not decided, use standard-library dataclasses and enums first.
- If Windows path handling breaks tests, fix helpers to use `pathlib.Path` exclusively.

## Open Questions

- Whether Python contract models should later generate TypeScript types, or whether TypeScript schemas should be authored separately in `packages/contracts`.
- Whether workspace creation belongs in `packages/workspace` only or should have a CLI in `tools/workspace/create_workspace.py` during Phase 0.
- Which real converter should be integrated first after the direct Markdown/text importer: Docling or MarkItDown.

---

### Task 1: Python Project And Contract Models

**Files:**
- Create: `pyproject.toml`
- Create: `packages/contracts/docagent_contracts/__init__.py`
- Create: `packages/contracts/docagent_contracts/models.py`
- Create: `packages/contracts/tests/test_models.py`
- Modify: `packages/contracts/README.md`

- [ ] **Step 1: Create minimal Python project config**

Create `pyproject.toml`:

```toml
[project]
name = "docagent-workbench"
version = "0.0.0"
requires-python = ">=3.11"
dependencies = []

[tool.pytest.ini_options]
pythonpath = [
  "packages/contracts",
  "packages/workspace",
  "packages/timeline",
  "tools/import"
]
testpaths = [
  "packages",
  "tools"
]
```

- [ ] **Step 2: Write failing contract tests**

Create `packages/contracts/tests/test_models.py`:

```python
from docagent_contracts import (
    Artifact,
    ArtifactKind,
    ConversionEngine,
    ConversionReport,
    ConversionStatus,
    DraftVersion,
    ImportedResource,
    ResourceScope,
    ResourceStatus,
    SemanticEventKind,
    SemanticTimelineEvent,
    TimelineActor,
    TimelineStatus,
    WorkspaceLayout,
)


def test_workspace_layout_defaults():
    layout = WorkspaceLayout(task_id="task-001", root="workspace/task-001")

    assert layout.brief_path == "brief.md"
    assert layout.inputs.markdown_dir == "inputs/markdown"
    assert layout.context.style_notes == "context/style_notes.md"
    assert layout.draft.current == "draft/draft.md"
    assert layout.reviews.checklist_result == "reviews/checklist_result.md"


def test_imported_resource_points_agent_to_markdown():
    resource = ImportedResource(
        id="res-001",
        scope=ResourceScope.TASK_INPUT,
        owner_id="task-001",
        source_path="inputs/original/brief.docx",
        markdown_path="inputs/markdown/brief.md",
        asset_dir="inputs/assets/brief",
        conversion_report_path="inputs/reports/brief.conversion.json",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        original_filename="brief.docx",
        status=ResourceStatus.CONVERTED,
        created_at="2026-04-30T00:00:00Z",
        updated_at="2026-04-30T00:00:00Z",
    )

    assert resource.markdown_path == "inputs/markdown/brief.md"
    assert resource.source_path.endswith(".docx")


def test_conversion_report_warning_shape():
    report = ConversionReport(
        source_path="inputs/original/example.pdf",
        markdown_path=None,
        asset_dir=None,
        engine=ConversionEngine.DOCLING,
        status=ConversionStatus.FAILED,
        warnings=[{"type": "unsupported", "message": "PDF conversion is not wired yet.", "location": None}],
        features_detected={"tables": 0, "images": 0, "formulas": 0, "footnotes": 0, "pages": None},
        created_at="2026-04-30T00:00:00Z",
    )

    assert report.warnings[0]["type"] == "unsupported"
    assert report.features_detected["pages"] is None


def test_semantic_timeline_event_shape():
    event = SemanticTimelineEvent(
        id="evt-001",
        session_id="session-001",
        task_id="task-001",
        actor=TimelineActor.TOOL,
        kind=SemanticEventKind.CREATE_CHECKPOINT,
        raw_event_id="raw-001",
        summary="Create checkpoint",
        paths=["versions/v001.md"],
        status=TimelineStatus.SUCCEEDED,
        created_at="2026-04-30T00:00:00Z",
    )

    assert event.kind is SemanticEventKind.CREATE_CHECKPOINT
    assert event.paths == ["versions/v001.md"]


def test_draft_version_and_artifact_shape():
    version = DraftVersion(
        id="ver-001",
        task_id="task-001",
        version="v001",
        source_path="draft/draft.md",
        version_path="versions/v001.md",
        summary="Initial draft",
        created_by="agent",
        created_at="2026-04-30T00:00:00Z",
    )
    artifact = Artifact(
        id="art-001",
        task_id="task-001",
        draft_version_id=version.id,
        kind=ArtifactKind.DOCX,
        path="artifacts/output.docx",
        status="created",
        created_at="2026-04-30T00:00:00Z",
    )

    assert version.version_path == "versions/v001.md"
    assert artifact.kind is ArtifactKind.DOCX
```

- [ ] **Step 3: Run tests and verify they fail**

Run:

```powershell
python -m pytest packages/contracts/tests/test_models.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'docagent_contracts'
```

- [ ] **Step 4: Implement contract models**

Create `packages/contracts/docagent_contracts/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ResourceScope(str, Enum):
    TASK_INPUT = "task_input"
    DOCTYPE_EXAMPLE = "doctype_example"
    DOCTYPE_SPEC = "doctype_spec"
    DOCTYPE_CHECKLIST = "doctype_checklist"
    EXPORT_REFERENCE = "export_reference"


class ResourceStatus(str, Enum):
    PENDING = "pending"
    CONVERTING = "converting"
    CONVERTED = "converted"
    FAILED = "failed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ConversionEngine(str, Enum):
    DOCLING = "docling"
    MARKITDOWN = "markitdown"
    PANDOC = "pandoc"
    MINERU = "mineru"
    MARKER = "marker"
    MANUAL = "manual"
    UNKNOWN = "unknown"


class ConversionStatus(str, Enum):
    SUCCEEDED = "succeeded"
    SUCCEEDED_WITH_WARNINGS = "succeeded_with_warnings"
    FAILED = "failed"


class TimelineActor(str, Enum):
    USER = "user"
    AGENT = "agent"
    TOOL = "tool"
    SYSTEM = "system"


class SemanticEventKind(str, Enum):
    USER_MESSAGE = "user_message"
    AGENT_MESSAGE = "agent_message"
    READ_SKILL = "read_skill"
    ANALYZE_EXAMPLES = "analyze_examples"
    EXTRACT_STYLE = "extract_style"
    EXTRACT_STRUCTURE = "extract_structure"
    GENERATE_OUTLINE = "generate_outline"
    UPDATE_DRAFT = "update_draft"
    CREATE_CHECKPOINT = "create_checkpoint"
    RUN_CHECKLIST = "run_checklist"
    EXPORT_DOCX = "export_docx"
    EXPORT_PDF = "export_pdf"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_RESOLVED = "approval_resolved"
    ERROR = "error"


class TimelineStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class ArtifactKind(str, Enum):
    MARKDOWN = "markdown"
    DOCX = "docx"
    PDF = "pdf"


@dataclass(frozen=True)
class InputPaths:
    original_dir: str = "inputs/original"
    markdown_dir: str = "inputs/markdown"
    assets_dir: str = "inputs/assets"
    reports_dir: str = "inputs/reports"


@dataclass(frozen=True)
class ContextPaths:
    user_intent: str = "context/user_intent.md"
    doc_map: str = "context/doc_map.md"
    style_notes: str = "context/style_notes.md"
    structure_notes: str = "context/structure_notes.md"
    decision_log: str = "context/decision_log.md"
    open_questions: str = "context/open_questions.md"
    draft_summary: str = "context/draft_summary.md"


@dataclass(frozen=True)
class DraftPaths:
    outline: str = "draft/outline.md"
    current: str = "draft/draft.md"
    sections_dir: str = "draft/sections"


@dataclass(frozen=True)
class ReviewPaths:
    checklist_result: str = "reviews/checklist_result.md"
    self_review: str = "reviews/self_review.md"


@dataclass(frozen=True)
class LogPaths:
    agent_notes: str = "logs/agent_notes.md"


@dataclass(frozen=True)
class WorkspaceLayout:
    task_id: str
    root: str
    brief_path: str = "brief.md"
    inputs: InputPaths = field(default_factory=InputPaths)
    context: ContextPaths = field(default_factory=ContextPaths)
    draft: DraftPaths = field(default_factory=DraftPaths)
    versions_dir: str = "versions"
    reviews: ReviewPaths = field(default_factory=ReviewPaths)
    artifacts_dir: str = "artifacts"
    logs: LogPaths = field(default_factory=LogPaths)


@dataclass(frozen=True)
class ImportedResource:
    id: str
    scope: ResourceScope
    owner_id: str
    source_path: str
    markdown_path: str | None
    asset_dir: str | None
    conversion_report_path: str | None
    mime_type: str
    original_filename: str
    status: ResourceStatus
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ConversionReport:
    source_path: str
    markdown_path: str | None
    asset_dir: str | None
    engine: ConversionEngine
    status: ConversionStatus
    warnings: list[dict[str, Any]]
    features_detected: dict[str, int | None]
    created_at: str


@dataclass(frozen=True)
class SemanticTimelineEvent:
    id: str
    session_id: str
    task_id: str
    actor: TimelineActor
    kind: SemanticEventKind
    raw_event_id: str | None
    summary: str
    paths: list[str]
    status: TimelineStatus
    created_at: str


@dataclass(frozen=True)
class DraftVersion:
    id: str
    task_id: str
    version: str
    source_path: str
    version_path: str
    summary: str
    created_by: str
    created_at: str


@dataclass(frozen=True)
class Artifact:
    id: str
    task_id: str
    draft_version_id: str | None
    kind: ArtifactKind
    path: str
    status: str
    created_at: str
```

Create `packages/contracts/docagent_contracts/__init__.py`:

```python
from .models import (
    Artifact,
    ArtifactKind,
    ConversionEngine,
    ConversionReport,
    ConversionStatus,
    DraftVersion,
    ImportedResource,
    ResourceScope,
    ResourceStatus,
    SemanticEventKind,
    SemanticTimelineEvent,
    TimelineActor,
    TimelineStatus,
    WorkspaceLayout,
)

__all__ = [
    "Artifact",
    "ArtifactKind",
    "ConversionEngine",
    "ConversionReport",
    "ConversionStatus",
    "DraftVersion",
    "ImportedResource",
    "ResourceScope",
    "ResourceStatus",
    "SemanticEventKind",
    "SemanticTimelineEvent",
    "TimelineActor",
    "TimelineStatus",
    "WorkspaceLayout",
]
```

- [ ] **Step 5: Run contract tests**

Run:

```powershell
python -m pytest packages/contracts/tests/test_models.py -q
```

Expected:

```text
5 passed
```

- [ ] **Step 6: Document model location**

Append to `packages/contracts/README.md`:

```markdown

## Phase 0 Python Models

The first executable contract models live in `docagent_contracts/models.py`.

These models intentionally use the Python standard library so Phase 0 can start without dependency decisions. If generated TypeScript or Pydantic models are added later, keep field names aligned with `schemas.md`.
```

- [ ] **Step 7: Commit Task 1**

Run:

```powershell
git add pyproject.toml packages/contracts
git commit -m "Add phase 0 contract models"
```

### Task 2: Workspace Layout And Validation

**Files:**
- Create: `packages/workspace/docagent_workspace/__init__.py`
- Create: `packages/workspace/docagent_workspace/layout.py`
- Create: `packages/workspace/docagent_workspace/validation.py`
- Create: `packages/workspace/tests/test_layout.py`
- Create: `packages/workspace/tests/test_validation.py`
- Modify: `packages/workspace/README.md`

- [ ] **Step 1: Write failing workspace layout tests**

Create `packages/workspace/tests/test_layout.py`:

```python
from pathlib import Path

from docagent_workspace import create_workspace, workspace_paths


def test_create_workspace_creates_contract_dirs(tmp_path: Path):
    root = tmp_path / "task-001"

    create_workspace(root, brief="Write a PRD.")

    assert (root / "brief.md").read_text(encoding="utf-8") == "Write a PRD.\n"
    assert (root / "inputs/original").is_dir()
    assert (root / "inputs/markdown").is_dir()
    assert (root / "inputs/assets").is_dir()
    assert (root / "inputs/reports").is_dir()
    assert (root / "context").is_dir()
    assert (root / "draft/sections").is_dir()
    assert (root / "versions").is_dir()
    assert (root / "reviews").is_dir()
    assert (root / "artifacts").is_dir()
    assert (root / "logs").is_dir()


def test_workspace_paths_returns_expected_files(tmp_path: Path):
    paths = workspace_paths(tmp_path / "task-001")

    assert paths.brief == tmp_path / "task-001" / "brief.md"
    assert paths.current_draft == tmp_path / "task-001" / "draft" / "draft.md"
    assert paths.style_notes == tmp_path / "task-001" / "context" / "style_notes.md"
```

- [ ] **Step 2: Write failing validation tests**

Create `packages/workspace/tests/test_validation.py`:

```python
from pathlib import Path

from docagent_workspace import create_workspace, validate_workspace


def test_validate_workspace_reports_missing_required_files(tmp_path: Path):
    root = tmp_path / "task-001"
    create_workspace(root, brief="Write a PRD.")

    result = validate_workspace(root)

    assert not result.valid
    assert "context/user_intent.md" in result.missing_files
    assert "context/style_notes.md" in result.missing_files
    assert "context/structure_notes.md" in result.missing_files
    assert "draft/outline.md" in result.missing_files


def test_validate_workspace_passes_when_required_files_exist(tmp_path: Path):
    root = tmp_path / "task-001"
    create_workspace(root, brief="Write a PRD.")
    for path in [
        "context/user_intent.md",
        "context/style_notes.md",
        "context/structure_notes.md",
        "draft/outline.md",
    ]:
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# ok\n", encoding="utf-8")

    result = validate_workspace(root)

    assert result.valid
    assert result.missing_files == []
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```powershell
python -m pytest packages/workspace/tests/test_layout.py packages/workspace/tests/test_validation.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'docagent_workspace'
```

- [ ] **Step 4: Implement workspace helpers**

Create `packages/workspace/docagent_workspace/layout.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


WORKSPACE_DIRS = [
    "inputs/original",
    "inputs/markdown",
    "inputs/assets",
    "inputs/reports",
    "context",
    "draft/sections",
    "versions",
    "reviews",
    "artifacts",
    "logs",
]


@dataclass(frozen=True)
class WorkspacePaths:
    root: Path
    brief: Path
    user_intent: Path
    style_notes: Path
    structure_notes: Path
    outline: Path
    current_draft: Path


def workspace_paths(root: Path) -> WorkspacePaths:
    return WorkspacePaths(
        root=root,
        brief=root / "brief.md",
        user_intent=root / "context" / "user_intent.md",
        style_notes=root / "context" / "style_notes.md",
        structure_notes=root / "context" / "structure_notes.md",
        outline=root / "draft" / "outline.md",
        current_draft=root / "draft" / "draft.md",
    )


def create_workspace(root: Path, brief: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for rel_dir in WORKSPACE_DIRS:
        (root / rel_dir).mkdir(parents=True, exist_ok=True)
    brief_text = brief if brief.endswith("\n") else f"{brief}\n"
    (root / "brief.md").write_text(brief_text, encoding="utf-8")
```

Create `packages/workspace/docagent_workspace/validation.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


REQUIRED_BEFORE_DRAFTING = [
    "context/user_intent.md",
    "context/style_notes.md",
    "context/structure_notes.md",
    "draft/outline.md",
]


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    missing_files: list[str]


def validate_workspace(root: Path) -> ValidationResult:
    missing = [path for path in REQUIRED_BEFORE_DRAFTING if not (root / path).is_file()]
    return ValidationResult(valid=not missing, missing_files=missing)
```

Create `packages/workspace/docagent_workspace/__init__.py`:

```python
from .layout import WORKSPACE_DIRS, WorkspacePaths, create_workspace, workspace_paths
from .validation import REQUIRED_BEFORE_DRAFTING, ValidationResult, validate_workspace

__all__ = [
    "REQUIRED_BEFORE_DRAFTING",
    "WORKSPACE_DIRS",
    "ValidationResult",
    "WorkspacePaths",
    "create_workspace",
    "validate_workspace",
    "workspace_paths",
]
```

- [ ] **Step 5: Run tests**

Run:

```powershell
python -m pytest packages/workspace/tests/test_layout.py packages/workspace/tests/test_validation.py -q
```

Expected:

```text
4 passed
```

- [ ] **Step 6: Update workspace README**

Append to `packages/workspace/README.md`:

```markdown

## Phase 0 Helpers

Executable helpers live in `docagent_workspace/`.

- `create_workspace(root, brief)`: creates the Markdown-only task workspace directories and `brief.md`.
- `validate_workspace(root)`: checks required pre-drafting files.
- `workspace_paths(root)`: returns common contract paths.
```

- [ ] **Step 7: Commit Task 2**

Run:

```powershell
git add packages/workspace
git commit -m "Add workspace creation and validation"
```

### Task 3: Checkpoint Helper And Workspace CLIs

**Files:**
- Create: `packages/workspace/docagent_workspace/checkpoint.py`
- Create: `packages/workspace/tests/test_checkpoint.py`
- Create: `tools/workspace/validate_workspace.py`
- Create: `tools/workspace/checkpoint.py`
- Modify: `tools/workspace/README.md`

- [ ] **Step 1: Write failing checkpoint tests**

Create `packages/workspace/tests/test_checkpoint.py`:

```python
from pathlib import Path

from docagent_workspace import checkpoint_draft, create_workspace


def test_checkpoint_draft_creates_first_version(tmp_path: Path):
    root = tmp_path / "task-001"
    create_workspace(root, brief="Write a PRD.")
    (root / "draft" / "draft.md").write_text("# Draft\n", encoding="utf-8")

    version = checkpoint_draft(root, summary="Initial draft")

    assert version.version == "v001"
    assert version.version_path == "versions/v001.md"
    assert (root / "versions" / "v001.md").read_text(encoding="utf-8") == "# Draft\n"


def test_checkpoint_draft_increments_versions(tmp_path: Path):
    root = tmp_path / "task-001"
    create_workspace(root, brief="Write a PRD.")
    (root / "draft" / "draft.md").write_text("# Draft 1\n", encoding="utf-8")
    checkpoint_draft(root, summary="Initial draft")
    (root / "draft" / "draft.md").write_text("# Draft 2\n", encoding="utf-8")

    version = checkpoint_draft(root, summary="Second draft")

    assert version.version == "v002"
    assert version.version_path == "versions/v002.md"
    assert (root / "versions" / "v002.md").read_text(encoding="utf-8") == "# Draft 2\n"


def test_checkpoint_requires_current_draft(tmp_path: Path):
    root = tmp_path / "task-001"
    create_workspace(root, brief="Write a PRD.")

    try:
        checkpoint_draft(root, summary="Missing draft")
    except FileNotFoundError as exc:
        assert "draft/draft.md" in str(exc)
    else:
        raise AssertionError("Expected FileNotFoundError")
```

- [ ] **Step 2: Run checkpoint tests and verify failure**

Run:

```powershell
python -m pytest packages/workspace/tests/test_checkpoint.py -q
```

Expected:

```text
ImportError: cannot import name 'checkpoint_draft'
```

- [ ] **Step 3: Implement checkpoint helper**

Create `packages/workspace/docagent_workspace/checkpoint.py`:

```python
from __future__ import annotations

import shutil
from pathlib import Path

from docagent_contracts import DraftVersion


def _next_version(root: Path) -> tuple[str, Path]:
    versions_dir = root / "versions"
    versions_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(versions_dir.glob("v*.md"))
    next_index = len(existing) + 1
    version = f"v{next_index:03d}"
    return version, versions_dir / f"{version}.md"


def checkpoint_draft(root: Path, summary: str, created_at: str = "1970-01-01T00:00:00Z") -> DraftVersion:
    source = root / "draft" / "draft.md"
    if not source.is_file():
        raise FileNotFoundError("Cannot checkpoint missing draft/draft.md")

    version, target = _next_version(root)
    shutil.copyfile(source, target)
    return DraftVersion(
        id=version,
        task_id=root.name,
        version=version,
        source_path="draft/draft.md",
        version_path=f"versions/{version}.md",
        summary=summary,
        created_by="agent",
        created_at=created_at,
    )
```

Modify `packages/workspace/docagent_workspace/__init__.py`:

```python
from .checkpoint import checkpoint_draft
from .layout import WORKSPACE_DIRS, WorkspacePaths, create_workspace, workspace_paths
from .validation import REQUIRED_BEFORE_DRAFTING, ValidationResult, validate_workspace

__all__ = [
    "REQUIRED_BEFORE_DRAFTING",
    "WORKSPACE_DIRS",
    "ValidationResult",
    "WorkspacePaths",
    "checkpoint_draft",
    "create_workspace",
    "validate_workspace",
    "workspace_paths",
]
```

- [ ] **Step 4: Run checkpoint tests**

Run:

```powershell
python -m pytest packages/workspace/tests/test_checkpoint.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Create validation CLI**

Create `tools/workspace/validate_workspace.py`:

```python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "contracts"))
sys.path.insert(0, str(ROOT / "packages" / "workspace"))

from docagent_workspace import validate_workspace


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    args = parser.parse_args()

    result = validate_workspace(Path(args.workspace))
    if result.valid:
        print("valid")
        return 0

    print("invalid")
    for path in result.missing_files:
        print(f"missing: {path}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Create checkpoint CLI**

Create `tools/workspace/checkpoint.py`:

```python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "contracts"))
sys.path.insert(0, str(ROOT / "packages" / "workspace"))

from docagent_workspace import checkpoint_draft


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--summary", default="Checkpoint")
    args = parser.parse_args()

    version = checkpoint_draft(Path(args.workspace), summary=args.summary)
    print(version.version_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 7: Smoke test CLIs**

Run:

```powershell
$root = Join-Path $env:TEMP "docagent-checkpoint-smoke"
Remove-Item -Recurse -Force $root -ErrorAction SilentlyContinue
$env:PYTHONPATH = "packages/contracts;packages/workspace"
@'
from pathlib import Path
from docagent_workspace import create_workspace
root = Path(r"REPLACE_ROOT")
create_workspace(root, "Write a PRD.")
(root / "draft" / "draft.md").write_text("# Draft`n", encoding="utf-8")
'@.Replace("REPLACE_ROOT", $root.Replace("\", "\\")) | python -
python tools/workspace/checkpoint.py --workspace $root --summary "Initial draft"
python tools/workspace/validate_workspace.py --workspace $root
```

Expected:

```text
versions/v001.md
invalid
missing: context/user_intent.md
missing: context/style_notes.md
missing: context/structure_notes.md
missing: draft/outline.md
```

- [ ] **Step 8: Update tools README**

Append this text to `tools/workspace/README.md`:

````markdown

## Phase 0 Commands

```powershell
python tools/workspace/validate_workspace.py --workspace path/to/workspace
python tools/workspace/checkpoint.py --workspace path/to/workspace --summary "Before revision"
```
````

- [ ] **Step 9: Commit Task 3**

Run:

```powershell
git add packages/workspace tools/workspace
git commit -m "Add workspace checkpoint tools"
```

### Task 4: Markdown Import Stub

**Files:**
- Create: `tools/import/convert_to_markdown.py`
- Create: `tools/import/inspect_conversion.py`
- Create: `tools/import/tests/test_convert_to_markdown.py`
- Modify: `tools/import/README.md`

- [ ] **Step 1: Write failing import tests**

Create `tools/import/tests/test_convert_to_markdown.py`:

```python
import json
from pathlib import Path

from convert_to_markdown import convert_file


def test_convert_markdown_copies_to_markdown_dir(tmp_path: Path):
    source = tmp_path / "original" / "note.md"
    source.parent.mkdir()
    source.write_text("# Note\n", encoding="utf-8")
    output_root = tmp_path / "inputs"

    report_path = convert_file(source, output_root)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "succeeded"
    assert Path(report["markdown_path"]).name == "note.md"
    assert (output_root / "markdown" / "note.md").read_text(encoding="utf-8") == "# Note\n"


def test_convert_text_wraps_plain_text_as_markdown(tmp_path: Path):
    source = tmp_path / "original" / "note.txt"
    source.parent.mkdir()
    source.write_text("hello\n", encoding="utf-8")
    output_root = tmp_path / "inputs"

    report_path = convert_file(source, output_root)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "succeeded"
    assert (output_root / "markdown" / "note.md").read_text(encoding="utf-8") == "hello\n"


def test_unsupported_file_writes_failure_report(tmp_path: Path):
    source = tmp_path / "original" / "deck.pptx"
    source.parent.mkdir()
    source.write_bytes(b"not really a pptx")
    output_root = tmp_path / "inputs"

    report_path = convert_file(source, output_root)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert report["markdown_path"] is None
    assert report["warnings"][0]["type"] == "unsupported_format"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
$env:PYTHONPATH = "tools/import"
python -m pytest tools/import/tests/test_convert_to_markdown.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'convert_to_markdown'
```

- [ ] **Step 3: Implement import converter**

Create `tools/import/convert_to_markdown.py`:

```python
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


SUPPORTED_DIRECT = {".md", ".markdown", ".txt"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _report_path(output_root: Path, source: Path) -> Path:
    reports = output_root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    return reports / f"{source.stem}.conversion.json"


def convert_file(source: Path, output_root: Path) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "markdown").mkdir(parents=True, exist_ok=True)
    (output_root / "assets").mkdir(parents=True, exist_ok=True)
    report_path = _report_path(output_root, source)

    suffix = source.suffix.lower()
    markdown_path: Path | None = None
    warnings: list[dict[str, str | None]] = []
    status = "succeeded"

    if suffix in {".md", ".markdown"}:
        markdown_path = output_root / "markdown" / f"{source.stem}.md"
        shutil.copyfile(source, markdown_path)
    elif suffix == ".txt":
        markdown_path = output_root / "markdown" / f"{source.stem}.md"
        markdown_path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        status = "failed"
        warnings.append(
            {
                "type": "unsupported_format",
                "message": f"Phase 0 direct converter does not support {suffix or 'files without extension'}.",
                "location": None,
            }
        )

    report = {
        "source_path": str(source),
        "markdown_path": str(markdown_path) if markdown_path else None,
        "asset_dir": str(output_root / "assets" / source.stem) if markdown_path else None,
        "engine": "manual" if markdown_path else "unknown",
        "status": status,
        "warnings": warnings,
        "features_detected": {"tables": 0, "images": 0, "formulas": 0, "footnotes": 0, "pages": None},
        "created_at": _now(),
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()

    report_path = convert_file(Path(args.source), Path(args.output_root))
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Implement conversion inspector**

Create `tools/import/inspect_conversion.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    print(f"status: {report['status']}")
    print(f"engine: {report['engine']}")
    print(f"markdown: {report['markdown_path']}")
    for warning in report.get("warnings", []):
        print(f"warning[{warning['type']}]: {warning['message']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run import tests**

Run:

```powershell
$env:PYTHONPATH = "tools/import"
python -m pytest tools/import/tests/test_convert_to_markdown.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 6: Update import README**

Append this text to `tools/import/README.md`:

````markdown

## Phase 0 Support

The first converter only normalizes `.md`, `.markdown`, and `.txt` files. Unsupported files produce a failed conversion report instead of silently pretending conversion worked.

```powershell
python tools/import/convert_to_markdown.py --source path/to/input.md --output-root path/to/workspace/inputs
python tools/import/inspect_conversion.py --report path/to/workspace/inputs/reports/input.conversion.json
```
````

- [ ] **Step 7: Commit Task 4**

Run:

```powershell
git add tools/import
git commit -m "Add markdown import stub"
```

### Task 5: Timeline Semantic Mapper

**Files:**
- Create: `packages/timeline/docagent_timeline/__init__.py`
- Create: `packages/timeline/docagent_timeline/mapper.py`
- Create: `packages/timeline/tests/test_mapper.py`
- Modify: `packages/timeline/README.md`

- [ ] **Step 1: Write failing mapper tests**

Create `packages/timeline/tests/test_mapper.py`:

```python
from docagent_contracts import SemanticEventKind
from docagent_timeline import map_raw_event


def test_maps_skill_read():
    event = map_raw_event(
        raw_event_id="raw-001",
        task_id="task-001",
        session_id="session-001",
        actor="tool",
        action="read_file",
        path="/doc-types/prd/SKILL.md",
        command=None,
        status="succeeded",
        created_at="2026-04-30T00:00:00Z",
    )

    assert event.kind is SemanticEventKind.READ_SKILL
    assert event.summary == "Read document type skill"


def test_maps_style_notes_write():
    event = map_raw_event(
        raw_event_id="raw-002",
        task_id="task-001",
        session_id="session-001",
        actor="tool",
        action="write_file",
        path="context/style_notes.md",
        command=None,
        status="succeeded",
        created_at="2026-04-30T00:00:00Z",
    )

    assert event.kind is SemanticEventKind.EXTRACT_STYLE


def test_maps_checkpoint_command():
    event = map_raw_event(
        raw_event_id="raw-003",
        task_id="task-001",
        session_id="session-001",
        actor="tool",
        action="execute_bash",
        path=None,
        command="python tools/workspace/checkpoint.py --workspace x",
        status="succeeded",
        created_at="2026-04-30T00:00:00Z",
    )

    assert event.kind is SemanticEventKind.CREATE_CHECKPOINT
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest packages/timeline/tests/test_mapper.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'docagent_timeline'
```

- [ ] **Step 3: Implement mapper**

Create `packages/timeline/docagent_timeline/mapper.py`:

```python
from __future__ import annotations

from docagent_contracts import SemanticEventKind, SemanticTimelineEvent, TimelineActor, TimelineStatus


def _kind_and_summary(action: str, path: str | None, command: str | None) -> tuple[SemanticEventKind, str]:
    normalized_path = (path or "").replace("\\", "/")
    normalized_command = command or ""

    if normalized_path.endswith("/SKILL.md") or normalized_path.endswith("SKILL.md"):
        return SemanticEventKind.READ_SKILL, "Read document type skill"
    if "/examples/" in normalized_path and action == "read_file":
        return SemanticEventKind.ANALYZE_EXAMPLES, "Analyze best-practice examples"
    if normalized_path.endswith("context/style_notes.md"):
        return SemanticEventKind.EXTRACT_STYLE, "Extract style notes"
    if normalized_path.endswith("context/structure_notes.md"):
        return SemanticEventKind.EXTRACT_STRUCTURE, "Extract structure notes"
    if normalized_path.endswith("draft/outline.md"):
        return SemanticEventKind.GENERATE_OUTLINE, "Generate outline"
    if normalized_path.endswith("draft/draft.md"):
        return SemanticEventKind.UPDATE_DRAFT, "Update draft"
    if "checkpoint.py" in normalized_command:
        return SemanticEventKind.CREATE_CHECKPOINT, "Create checkpoint"
    if normalized_path.endswith("reviews/checklist_result.md"):
        return SemanticEventKind.RUN_CHECKLIST, "Run checklist"
    if "export_docx.py" in normalized_command:
        return SemanticEventKind.EXPORT_DOCX, "Export DOCX"

    return SemanticEventKind.AGENT_MESSAGE, "Agent event"


def map_raw_event(
    raw_event_id: str,
    task_id: str,
    session_id: str,
    actor: str,
    action: str,
    path: str | None,
    command: str | None,
    status: str,
    created_at: str,
) -> SemanticTimelineEvent:
    kind, summary = _kind_and_summary(action, path, command)
    paths = [path] if path else []
    return SemanticTimelineEvent(
        id=f"sem-{raw_event_id}",
        session_id=session_id,
        task_id=task_id,
        actor=TimelineActor(actor),
        kind=kind,
        raw_event_id=raw_event_id,
        summary=summary,
        paths=paths,
        status=TimelineStatus(status),
        created_at=created_at,
    )
```

Create `packages/timeline/docagent_timeline/__init__.py`:

```python
from .mapper import map_raw_event

__all__ = ["map_raw_event"]
```

- [ ] **Step 4: Run mapper tests**

Run:

```powershell
python -m pytest packages/timeline/tests/test_mapper.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Update timeline README**

Append to `packages/timeline/README.md`:

```markdown

## Phase 0 Mapper

`docagent_timeline.map_raw_event(...)` converts simple runtime signals into `SemanticTimelineEvent` objects.

The mapper is intentionally path- and command-based for Phase 0. Runtime-specific payload handling belongs in the future runtime adapter.
```

- [ ] **Step 6: Commit Task 5**

Run:

```powershell
git add packages/timeline
git commit -m "Add semantic timeline mapper"
```

### Task 6: GitHub Actions CI And Foundation Verification

Execution readiness: foundation tests pass locally.

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `docs/quality/testing.md`
- Modify: `docs/exec-plans/active/2026-04-30-phase-0-foundation.md`

- [ ] **Step 1: Extend GitHub Actions workflow**

Replace `.github/workflows/ci.yml` with:

```yaml
name: CI

on:
  push:
    branches:
      - main
  pull_request:

jobs:
  repository-structure:
    name: Repository structure
    runs-on: ubuntu-latest

    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Check required project docs
        shell: bash
        run: |
          set -euo pipefail
          test -f AGENTS.md
          test -f README.md
          test -f ARCHITECTURE.md
          test -f PLANS.md
          test -f docs/index.md
          test -f docs/product/vision.md
          test -f docs/product/ui-surfaces.md
          test -f docs/architecture/workspace-contract.md
          test -f docs/architecture/markdown-pipeline.md
          test -f docs/decisions/index.md

      - name: Check agent-friendly repo layout
        shell: bash
        run: |
          set -euo pipefail
          test -d apps/web
          test -d services/api
          test -d packages/contracts
          test -d packages/workspace
          test -d packages/doctypes
          test -d packages/timeline
          test -d agent/system-prompts
          test -d tools/import
          test -d tools/workspace
          test -d docs/exec-plans/active
          test -d docs/exec-plans/completed

      - name: Check PRD seed pack layout
        shell: bash
        run: |
          set -euo pipefail
          test -f doc-types/prd/SKILL.md
          test -d doc-types/prd/examples/original
          test -d doc-types/prd/examples/markdown
          test -d doc-types/prd/examples/assets
          test -d doc-types/prd/examples/reports
          test -d doc-types/prd/specs/original
          test -d doc-types/prd/specs/markdown
          test -d doc-types/prd/specs/assets
          test -d doc-types/prd/specs/reports
          test -f doc-types/prd/checklists/quality.yaml

  foundation:
    name: Foundation tests
    runs-on: ubuntu-latest

    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install test dependencies
        run: python -m pip install --upgrade pip pytest

      - name: Run foundation tests
        run: python -m pytest packages/contracts/tests packages/workspace/tests packages/timeline/tests tools/import/tests -q
```

- [ ] **Step 2: Run all foundation tests locally**

Run:

```powershell
python -m pytest packages/contracts/tests packages/workspace/tests packages/timeline/tests tools/import/tests -q
```

Expected:

```text
18 passed
```

If the exact count differs because tests were added or split, all collected tests must pass.

- [ ] **Step 3: Validate CI workflow content**

Run:

```powershell
Get-Content .github/workflows/ci.yml
```

Expected output includes:

```text
name: CI
pull_request:
python-version: "3.11"
python -m pytest packages/contracts/tests packages/workspace/tests packages/timeline/tests tools/import/tests -q
```

- [ ] **Step 4: Update testing docs**

Append this text to `docs/quality/testing.md`:

````markdown

## Phase 0 Foundation

Run foundation tests with:

```powershell
python -m pytest packages/contracts/tests packages/workspace/tests packages/timeline/tests tools/import/tests -q
```

These tests cover contract models, workspace creation, workspace validation, checkpoints, Markdown import stubs, and semantic timeline mapping.

GitHub Actions runs the same command in `.github/workflows/ci.yml` on push to `main` and pull requests.
````

- [ ] **Step 5: Mark this plan ready for execution**

In this file, add a short note under this task after tests pass:

```markdown
Execution readiness: foundation tests pass locally.
```

- [ ] **Step 6: Commit Task 6**

Run:

```powershell
git add .github/workflows/ci.yml docs/quality/testing.md docs/exec-plans/active/2026-04-30-phase-0-foundation.md
git commit -m "Add foundation CI"
```

## Self-Review

Spec coverage:

- Contract schema concern: Task 1.
- Workspace contract: Task 2 and Task 3.
- Markdown-only import boundary: Task 4.
- Semantic timeline: Task 5.
- CI and verification documentation: Task 6.

Placeholder scan:

- The plan intentionally uses "Open Questions" for unresolved architecture decisions, not implementation placeholders.
- No task contains unspecified code steps.

Type consistency:

- `ConversionReport`, `SemanticTimelineEvent`, and `DraftVersion` match `packages/contracts/schemas.md`.
- Workspace paths match `docs/architecture/workspace-contract.md`.
