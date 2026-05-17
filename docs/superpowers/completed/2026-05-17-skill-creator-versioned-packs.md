# Skill Creator Versioned Packs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build the MVP for material-driven Skill Creator over versioned document type packs, with draft pack workspaces, immutable published versions, and authoring tasks bound to published pack versions.

**Architecture:** Add a pack-management domain beside the existing authoring task/session domain. Store pack metadata and bindings in Postgres, keep mutable draft pack files and immutable published snapshots under product state storage, and use a management-scoped ACP-like Skill Creator session for observable generation and revision. Preserve the existing authoring loop while gradually resolving `doc_type_id` to a published pack version.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Postgres JSONB, existing ACP runtime adapter contract, existing import helpers, React 19, TanStack Query/Router, Vitest, pytest.

---

## Design Inputs

- Spec: `docs/superpowers/specs/2026-05-17-skill-creator-versioned-packs-design.md`
- Product guardrails: `docs/product/vision.md`, `docs/product/principles.md`, `docs/product/ui-surfaces.md`
- Conversion contract: `docs/architecture/markdown-pipeline.md`
- Current authoring routes: `services/api/docagent_api/routes/tasks.py`, `services/api/docagent_api/routes/sessions.py`
- Current document type reader: `services/api/docagent_api/doctypes.py`
- Current management stub: `apps/web/src/shell/SettingsDrawer.tsx`

## File Structure

- Create `services/api/docagent_api/skill_packs.py`: pure pack workspace, validation, resource conversion, publishing, and seed bootstrap helpers.
- Create `services/api/docagent_api/routes/skill_packs.py`: pack-management REST routes.
- Modify `services/api/docagent_api/db.py`: add pack, pack resource, pack version, pack artifact revision, Skill Creator session, and Skill Creator ACP event rows.
- Create `services/api/alembic/versions/0004_skill_packs.py`: migration for new rows and `tasks.pack_version_id`.
- Modify `services/api/docagent_api/state.py`: persistence helpers for packs, versions, resources, artifact revisions, management sessions, and management events.
- Modify `services/api/tests/conftest.py`: keep PostgreSQL test isolation aware of the new tables.
- Modify `services/api/docagent_api/request_models.py` and `services/api/docagent_api/response_models.py`: shared API shapes.
- Modify `services/api/docagent_api/app.py`: bootstrap seed packs and include the new router.
- Modify `services/api/docagent_api/prompts.py`: resolve authoring prompt bundles from published pack snapshots and add Skill Creator prompt bundles.
- Modify `services/api/docagent_api/routes/tasks.py`: bind new authoring tasks to a published pack version.
- Modify `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py`: support management-scoped Skill Creator actions for local tests.
- Modify `packages/contracts/docagent_contracts/models.py` and `packages/contracts/docagent_contracts/runtime.py`: add pack/session-scope enums and response-adjacent dataclasses.
- Modify `pyproject.toml`: make the YAML parser a runtime dependency for pack validation.
- Modify frontend API/types/hooks under `apps/web/src`: add skill-pack client types and TanStack Query hooks.
- Modify `apps/web/src/shell/SettingsDrawer.tsx`: replace the stub with the first pack-management surface.
- Modify `apps/web/src/App.tsx`: add a dedicated management route after drawer MVP is usable.

## Task 1: Pack Contracts, Database Rows, And State Helpers

**Files:**
- Modify: `packages/contracts/docagent_contracts/models.py`
- Modify: `packages/contracts/docagent_contracts/runtime.py`
- Modify: `packages/contracts/docagent_contracts/__init__.py`
- Modify: `packages/contracts/tests/test_models.py`
- Modify: `packages/contracts/tests/test_runtime_contracts.py`
- Modify: `services/api/docagent_api/db.py`
- Modify: `services/api/docagent_api/state.py`
- Modify: `services/api/tests/conftest.py`
- Create: `services/api/alembic/versions/0004_skill_packs.py`
- Create: `services/api/tests/test_skill_pack_state.py`

- [x] **Step 1: Write failing contract tests**

Add these tests to `packages/contracts/tests/test_models.py`:

```python
from docagent_contracts import PackResourceGroup, RuntimeSessionScope, SkillPackResourceStatus


def test_pack_resource_group_values_match_product_groups() -> None:
    assert [group.value for group in PackResourceGroup] == [
        "examples",
        "specs",
        "checklists",
        "export-references",
    ]


def test_runtime_session_scope_distinguishes_management_from_authoring() -> None:
    assert RuntimeSessionScope.AUTHORING.value == "authoring"
    assert RuntimeSessionScope.PACK_MANAGEMENT.value == "pack-management"


def test_skill_pack_resource_status_values_match_api_contract() -> None:
    assert [status.value for status in SkillPackResourceStatus] == ["ready", "warning", "failed", "unsupported"]
```

Add to `packages/contracts/tests/test_runtime_contracts.py`:

```python
def test_prompt_bundle_can_identify_pack_management_owner(tmp_path: Path) -> None:
    bundle = PromptBundle(
        system_prompt="system",
        task_instruction="task",
        workspace_root=tmp_path,
        doc_type_id="",
        pack_id="memo",
        metadata={"session_scope": "pack-management"},
    )

    assert bundle.pack_id == "memo"
    assert bundle.doc_type_id == ""
```

- [x] **Step 2: Run contract tests and verify the expected failure**

Run:

```powershell
python -m pytest packages/contracts/tests/test_models.py -q
```

Expected: FAIL with import errors for `PackResourceGroup`, `SkillPackResourceStatus`, and `RuntimeSessionScope`, or a `PromptBundle` constructor error for `pack_id`.

- [x] **Step 3: Add shared enum contracts**

In `packages/contracts/docagent_contracts/models.py`, add:

```python
class PackResourceGroup(str, Enum):
    EXAMPLES = "examples"
    SPECS = "specs"
    CHECKLISTS = "checklists"
    EXPORT_REFERENCES = "export-references"


class SkillPackResourceStatus(str, Enum):
    READY = "ready"
    WARNING = "warning"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"
```

In `packages/contracts/docagent_contracts/runtime.py`, add:

```python
class RuntimeSessionScope(str, Enum):
    AUTHORING = "authoring"
    PACK_MANAGEMENT = "pack-management"
```

In `PromptBundle`, add an optional management owner field without changing existing positional callers:

```python
@dataclass(frozen=True)
class PromptBundle:
    system_prompt: str
    task_instruction: str
    workspace_root: Path
    doc_type_id: str
    metadata: dict[str, Any] = field(default_factory=dict)
    pack_id: str | None = None
```

Export `PackResourceGroup`, `SkillPackResourceStatus`, and `RuntimeSessionScope` from `packages/contracts/docagent_contracts/__init__.py`.

- [x] **Step 4: Write failing state tests**

Create `services/api/tests/test_skill_pack_state.py`:

```python
from pathlib import Path

from docagent_api.state import DocAgentState


def test_skill_pack_rows_roundtrip(pg_state: DocAgentState) -> None:
    pg_state.save_skill_pack({
        "id": "risk-report",
        "title": "Risk Report",
        "description": "Enterprise risk review pack",
        "draft_status": "draft",
    })

    assert pg_state.get_skill_pack("risk-report")["title"] == "Risk Report"
    assert pg_state.list_skill_packs()[0]["id"] == "risk-report"


def test_skill_pack_version_rows_are_queryable(pg_state: DocAgentState, tmp_path: Path) -> None:
    pg_state.save_skill_pack({
        "id": "prd",
        "title": "PRD",
        "description": "Product requirements",
        "draft_status": "draft",
    })
    pg_state.save_skill_pack_version({
        "id": "prd-v001",
        "pack_id": "prd",
        "version": "v001",
        "snapshot_path": str(tmp_path / "snapshot"),
        "manifest": {"skill_path": "SKILL.md"},
        "validation": {"status": "passed", "warnings": []},
        "publish_note": "Seed version",
    })

    latest = pg_state.get_latest_skill_pack_version("prd")
    assert latest["id"] == "prd-v001"
    assert latest["version"] == "v001"
```

- [x] **Step 5: Run state tests and verify the expected failure**

Run:

```powershell
python -m pytest services/api/tests/test_skill_pack_state.py -q
```

Expected: FAIL because `save_skill_pack` and `save_skill_pack_version` do not exist.

- [x] **Step 6: Add database rows and Alembic migration**

In `services/api/docagent_api/db.py`, add row classes:

```python
class SkillPackRow(Base):
    __tablename__ = "skill_packs"
    id = Column(String, primary_key=True)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=False, default="")
    draft_status = Column(String, nullable=False, default="draft")
    latest_version_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class SkillPackResourceRow(Base):
    __tablename__ = "skill_pack_resources"
    id = Column(String, primary_key=True)
    pack_id = Column(String, ForeignKey("skill_packs.id"), nullable=False)
    group = Column(String, nullable=False)
    original_filename = Column(Text, nullable=False)
    source_path = Column(Text, nullable=False)
    markdown_path = Column(Text)
    conversion_report_path = Column(Text, nullable=False)
    status = Column(String, nullable=False)
    summary = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (Index("idx_skill_pack_resources_pack", "pack_id"),)


class SkillPackVersionRow(Base):
    __tablename__ = "skill_pack_versions"
    id = Column(String, primary_key=True)
    pack_id = Column(String, ForeignKey("skill_packs.id"), nullable=False)
    version = Column(String, nullable=False)
    snapshot_path = Column(Text, nullable=False)
    manifest = Column(JSONB, nullable=False)
    validation = Column(JSONB, nullable=False)
    publish_note = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_skill_pack_versions_pack", "pack_id", "version"),
        CheckConstraint("version <> ''", name="ck_skill_pack_versions_nonempty"),
    )


class SkillPackArtifactRevisionRow(Base):
    __tablename__ = "skill_pack_artifact_revisions"
    id = Column(String, primary_key=True)
    pack_id = Column(String, ForeignKey("skill_packs.id"), nullable=False)
    artifact_path = Column(Text, nullable=False)
    content_sha256 = Column(String, nullable=False)
    source = Column(String, nullable=False)
    summary = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (Index("idx_skill_pack_artifact_revisions_pack", "pack_id", "created_at"),)


class SkillCreatorSessionRow(Base):
    __tablename__ = "skill_creator_sessions"
    id = Column(String, primary_key=True)
    pack_id = Column(String, ForeignKey("skill_packs.id"), nullable=False)
    session_scope = Column(String, nullable=False, default="pack-management")
    status = Column(String, nullable=False)
    runtime = Column(String)
    runtime_session_id = Column(String)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (Index("idx_skill_creator_sessions_pack", "pack_id"),)


class SkillCreatorEventRow(Base):
    __tablename__ = "skill_creator_events"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("skill_creator_sessions.id"), nullable=False)
    event_type = Column(String, nullable=False)
    payload = Column(JSONB, nullable=False)
    projection = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (Index("idx_skill_creator_events_session", "session_id", "id"),)
```

In `TaskRow`, add:

```python
pack_version_id = Column(String, ForeignKey("skill_pack_versions.id"), nullable=True)
```

Create `services/api/alembic/versions/0004_skill_packs.py` with idempotent table creation for these tables and an idempotent `pack_version_id` column addition to `tasks`.

- [x] **Step 7: Add state methods**

In `services/api/docagent_api/state.py`, add concrete persistence methods with these behaviors:

- `save_skill_pack`: upsert the pack row and preserve `latest_version_id` unless the caller supplies it.
- `get_skill_pack` and `list_skill_packs`: return row dictionaries sorted by pack id for stable tests.
- `save_skill_pack_resource` and `list_skill_pack_resources`: persist resource metadata and return resources in creation order.
- `save_skill_pack_version`: insert the immutable version row and update the parent pack's `latest_version_id`.
- `get_skill_pack_version`, `list_skill_pack_versions`, and `get_latest_skill_pack_version`: fetch versions by id, by pack id, and by the parent pack pointer.
- `save_skill_pack_artifact_revision`: insert each artifact revision record.
- `save_skill_creator_session` and `get_skill_creator_session`: persist management session rows separately from authoring sessions.
- `append_skill_creator_event` and `list_skill_creator_events`: append and read ordered management ACP event projections.
- `skill_pack_root`: return `self.root / "skill-packs" / pack_id`.

Keep row-to-dict helpers next to existing `_task_row_to_dict` helpers.

Update `services/api/tests/conftest.py` so the PostgreSQL fixture truncates all authoring and pack-management tables:

```python
conn.execute(text(
    "TRUNCATE skill_creator_events, skill_creator_sessions, "
    "skill_pack_artifact_revisions, skill_pack_resources, "
    "acp_events, raw_runtime_events, timeline_events, sessions, tasks, "
    "skill_pack_versions, skill_packs "
    "RESTART IDENTITY CASCADE"
))
```

The explicit child-before-parent order keeps the statement readable; `CASCADE` handles the `tasks.pack_version_id` relationship once Task 5 adds it.

- [x] **Step 8: Run Task 1 verification**

Run:

```powershell
python -m pytest packages/contracts/tests/test_models.py services/api/tests/test_skill_pack_state.py -q
```

Expected: PASS.

- [x] **Step 9: Commit Task 1**

```powershell
git add packages/contracts services/api/docagent_api/db.py services/api/docagent_api/state.py services/api/alembic/versions/0004_skill_packs.py services/api/tests/conftest.py services/api/tests/test_skill_pack_state.py
git commit -m "feat: add skill pack persistence model"
```

## Task 2: Pack Workspace, Seed Bootstrap, And Validation

**Files:**
- Create: `services/api/docagent_api/skill_packs.py`
- Modify: `pyproject.toml`
- Modify: `services/api/docagent_api/app.py`
- Modify: `services/api/docagent_api/state.py`
- Modify: `services/api/tests/test_skill_pack_state.py`
- Create: `services/api/tests/test_skill_packs.py`

- [x] **Step 1: Write failing workspace and bootstrap tests**

Create `services/api/tests/test_skill_packs.py`:

```python
from pathlib import Path

from docagent_api.skill_packs import (
    bootstrap_seed_skill_packs,
    publish_skill_pack_snapshot,
    validate_skill_pack_draft,
    write_skill_pack_artifact,
)
from docagent_api.state import DocAgentState


def test_bootstrap_seed_prd_pack_creates_published_snapshot(tmp_path: Path) -> None:
    state = DocAgentState(tmp_path / "state")
    bootstrap_seed_skill_packs(state, Path("doc-types"))

    pack = state.get_skill_pack("prd")
    latest = state.get_latest_skill_pack_version("prd")
    assert pack["title"] == "PRD"
    assert latest["version"] == "v001"
    assert (Path(latest["snapshot_path"]) / "SKILL.md").is_file()


def test_validate_skill_pack_blocks_missing_skill(tmp_path: Path) -> None:
    state = DocAgentState(tmp_path / "state")
    state.save_skill_pack({"id": "memo", "title": "Memo", "description": "", "draft_status": "draft"})

    result = validate_skill_pack_draft(state, "memo")

    assert result["status"] == "failed"
    assert "SKILL.md is missing" in result["errors"]


def test_publish_snapshot_is_immutable_after_draft_edit(tmp_path: Path) -> None:
    state = DocAgentState(tmp_path / "state")
    state.save_skill_pack({"id": "memo", "title": "Memo", "description": "", "draft_status": "draft"})
    write_skill_pack_artifact(state, "memo", "SKILL.md", "---\nname: memo\ndescription: Use for memos.\n---\n\n# Memo\n", "user", "Initial skill")
    version = publish_skill_pack_snapshot(state, "memo", "First version")
    write_skill_pack_artifact(state, "memo", "SKILL.md", "---\nname: memo\ndescription: Changed.\n---\n\n# Changed\n", "user", "Edit draft")

    assert "Use for memos." in (Path(version["snapshot_path"]) / "SKILL.md").read_text(encoding="utf-8")
```

- [x] **Step 2: Run tests and verify expected failure**

Run:

```powershell
python -m pytest services/api/tests/test_skill_packs.py -q
```

Expected: FAIL because `docagent_api.skill_packs` does not exist.

- [x] **Step 3: Implement pack workspace helpers**

Move `PyYAML>=6.0` from the dev optional dependencies into `[project].dependencies` in `pyproject.toml`, because API pack validation imports `yaml` at runtime.

Create `services/api/docagent_api/skill_packs.py` with these public functions:

```python
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from docagent_api.state import DocAgentState
from docagent_api.time import utc_now

PACK_GROUPS = ("examples", "specs", "checklists", "export-references")
ARTIFACT_TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".json"}


def is_valid_pack_id(pack_id: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", pack_id))


def draft_root(state: DocAgentState, pack_id: str) -> Path:
    return state.skill_pack_root(pack_id) / "draft"


def published_root(state: DocAgentState, pack_id: str, version: str) -> Path:
    return state.skill_pack_root(pack_id) / "published" / version


def write_skill_pack_artifact(
    state: DocAgentState,
    pack_id: str,
    relative_path: str,
    content: str,
    source: str,
    summary: str,
) -> dict[str, Any]:
    path = _resolve_artifact_path(draft_root(state, pack_id), relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = content if content.endswith("\n") else f"{content}\n"
    path.write_text(text, encoding="utf-8")
    revision = {
        "id": f"rev-{uuid4().hex[:12]}",
        "pack_id": pack_id,
        "artifact_path": relative_path,
        "content_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "source": source,
        "summary": summary,
    }
    state.save_skill_pack_artifact_revision(revision)
    return revision


def validate_skill_pack_draft(state: DocAgentState, pack_id: str) -> dict[str, Any]:
    root = draft_root(state, pack_id)
    errors: list[str] = []
    warnings: list[str] = []
    skill_path = root / "SKILL.md"
    if not skill_path.is_file():
        errors.append("SKILL.md is missing")
    else:
        content = skill_path.read_text(encoding="utf-8")
        if not content.strip():
            errors.append("SKILL.md is empty")
        if not content.startswith("---"):
            errors.append("SKILL.md frontmatter is missing")
        else:
            try:
                _frontmatter, _body = content.split("---", 2)[1:]
                parsed = yaml.safe_load(_frontmatter) or {}
                if not parsed.get("name") or not parsed.get("description"):
                    errors.append("SKILL.md frontmatter must include name and description")
            except (ValueError, yaml.YAMLError) as exc:
                errors.append(f"SKILL.md frontmatter is invalid: {exc}")
        if len(content.split()) > 2000:
            warnings.append("SKILL.md is over the MVP 2,000 word size limit")
        warnings.extend(_source_copy_warnings(root, content, state.list_skill_pack_resources(pack_id)))
    for checklist in sorted((root / "checklists").glob("*.y*ml")):
        try:
            yaml.safe_load(checklist.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            errors.append(f"{checklist.relative_to(root).as_posix()} is invalid YAML: {exc}")
    return {"status": "failed" if errors else "passed", "errors": errors, "warnings": warnings}


def publish_skill_pack_snapshot(state: DocAgentState, pack_id: str, publish_note: str) -> dict[str, Any]:
    validation = validate_skill_pack_draft(state, pack_id)
    if validation["status"] != "passed":
        raise ValueError("; ".join(validation["errors"]))
    version = _next_version(state, pack_id)
    target = published_root(state, pack_id, version)
    if target.exists():
        raise FileExistsError(target)
    shutil.copytree(draft_root(state, pack_id), target)
    manifest = _snapshot_manifest(target)
    record = {
        "id": f"{pack_id}-{version}",
        "pack_id": pack_id,
        "version": version,
        "snapshot_path": str(target),
        "manifest": manifest,
        "validation": validation,
        "publish_note": publish_note,
    }
    state.save_skill_pack_version(record)
    return state.get_latest_skill_pack_version(pack_id)
```

Add these private helpers in the same file:

```python
def _resolve_artifact_path(root: Path, relative_path: str) -> Path:
    target = (root / relative_path).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError("Artifact path escapes pack workspace")
    if target.suffix not in ARTIFACT_TEXT_SUFFIXES and target.name != "SKILL.md":
        raise ValueError("Only text skill artifacts are supported")
    return target


def _next_version(state: DocAgentState, pack_id: str) -> str:
    versions = state.list_skill_pack_versions(pack_id)
    return f"v{len(versions) + 1:03d}"


def _snapshot_manifest(root: Path) -> dict[str, Any]:
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        content = path.read_bytes()
        files.append({
            "path": path.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(content).hexdigest(),
            "size": len(content),
        })
    return {"files": files}


def _source_copy_warnings(root: Path, skill_content: str, resources: list[dict[str, Any]]) -> list[str]:
    skill_words = re.findall(r"\w+", skill_content.lower())
    if len(skill_words) < 25:
        return []
    skill_runs = {" ".join(skill_words[index:index + 25]) for index in range(len(skill_words) - 24)}
    warnings: list[str] = []
    for resource in resources:
        if resource["group"] not in {"examples", "specs"} or resource["status"] != "ready":
            continue
        markdown_path = resource.get("markdown_path")
        if not markdown_path:
            continue
        resource_path = root / markdown_path
        if not resource_path.is_file():
            continue
        resource_words = re.findall(r"\w+", resource_path.read_text(encoding="utf-8").lower())
        for index in range(max(0, len(resource_words) - 24)):
            if " ".join(resource_words[index:index + 25]) in skill_runs:
                warnings.append(f"SKILL.md shares 25+ consecutive words with {resource['original_filename']}")
                break
    return warnings
```

`bootstrap_seed_skill_packs` is implemented in Step 4.

- [x] **Step 4: Implement seed bootstrap**

In `bootstrap_seed_skill_packs(state, seed_root)`, scan `doc-types/*`, create pack rows, copy the seed pack into `state.skill_pack_root(pack_id)/draft`, and publish `v001` when no version exists. Use the seed `SKILL.md` as-is. Use title `path.name.upper()` for current seed packs.

Do not let one malformed seed pack prevent API startup. Wrap each pack bootstrap in a `try/except Exception`, log `logger.warning("Failed to bootstrap seed skill pack %s: %s", pack_id, exc)`, and continue scanning the remaining seed packs. The direct `test_bootstrap_seed_prd_pack_creates_published_snapshot` still asserts the normal PRD path succeeds.

In `services/api/docagent_api/app.py`, after the `DocAgentState` constructor call, call:

```python
from docagent_api.skill_packs import bootstrap_seed_skill_packs

bootstrap_seed_skill_packs(state, root / "doc-types")
```

- [x] **Step 5: Run Task 2 verification**

Run:

```powershell
python -m pytest services/api/tests/test_skill_packs.py services/api/tests/test_api.py::test_doc_type_endpoints -q
```

Expected: PASS.

- [x] **Step 6: Commit Task 2**

```powershell
git add pyproject.toml services/api/docagent_api/skill_packs.py services/api/docagent_api/app.py services/api/tests/test_skill_packs.py
git commit -m "feat: bootstrap versioned skill packs"
```

## Task 3: Pack Resource, Artifact, Validation, And Publish Routes

**Files:**
- Modify: `services/api/docagent_api/request_models.py`
- Modify: `services/api/docagent_api/response_models.py`
- Create: `services/api/docagent_api/routes/skill_packs.py`
- Modify: `services/api/docagent_api/app.py`
- Modify: `services/api/docagent_api/skill_packs.py`
- Create: `services/api/tests/test_skill_pack_routes.py`

- [x] **Step 1: Write failing route tests**

Create `services/api/tests/test_skill_pack_routes.py`:

```python
from pathlib import Path

from fastapi.testclient import TestClient

from docagent_api.app import create_app


def test_create_pack_add_resource_validate_and_publish(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))

    created = client.post("/skill-packs", json={
        "id": "risk-report",
        "title": "Risk Report",
        "description": "Board risk memo pack",
    })
    assert created.status_code == 200
    assert created.json()["id"] == "risk-report"

    resource = client.post("/skill-packs/risk-report/resources/text", json={
        "group": "examples",
        "name": "example.txt",
        "content": "Strong reports begin with material risk and mitigation owner.",
    })
    assert resource.status_code == 200
    assert resource.json()["status"] == "ready"
    assert resource.json()["markdown_path"].endswith(".md")

    artifact = client.put("/skill-packs/risk-report/artifacts", json={
        "path": "SKILL.md",
        "content": "---\nname: risk-report\ndescription: Use for enterprise risk reports.\n---\n\n# Risk Report\n",
        "summary": "Human-authored initial skill",
    })
    assert artifact.status_code == 200

    validation = client.post("/skill-packs/risk-report/validate").json()
    assert validation["status"] == "passed"

    published = client.post("/skill-packs/risk-report/publish", json={"publish_note": "First version"})
    assert published.status_code == 200
    assert published.json()["version"] == "v001"


def test_pack_artifact_path_traversal_is_rejected(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))
    client.post("/skill-packs", json={"id": "memo", "title": "Memo", "description": ""})

    response = client.put("/skill-packs/memo/artifacts", json={
        "path": "../outside.md",
        "content": "# Nope\n",
        "summary": "Traversal attempt",
    })

    assert response.status_code == 400
```

- [x] **Step 2: Run route tests and verify expected failure**

Run:

```powershell
python -m pytest services/api/tests/test_skill_pack_routes.py -q
```

Expected: FAIL because `/skill-packs` routes are not registered.

- [x] **Step 3: Add request and response models**

In `services/api/docagent_api/request_models.py`, add:

```python
class CreateSkillPackRequest(BaseModel):
    id: str
    title: str
    description: str = ""


class AddSkillPackTextResourceRequest(BaseModel):
    group: Literal["examples", "specs", "checklists", "export-references"]
    name: str
    content: str


class UpdateSkillPackArtifactRequest(BaseModel):
    path: str
    content: str
    summary: str


class PublishSkillPackRequest(BaseModel):
    publish_note: str = ""
    acknowledged_warnings: list[str] = Field(default_factory=list)
```

In `services/api/docagent_api/response_models.py`, add:

```python
class SkillPackSummaryResponse(BaseModel):
    id: str
    title: str
    description: str
    draft_status: str
    latest_version_id: str | None = None


class SkillPackResourceResponse(BaseModel):
    id: str
    pack_id: str
    group: str
    original_filename: str
    source_path: str
    markdown_path: str | None = None
    conversion_report_path: str
    status: str
    summary: str = ""


class SkillPackArtifactResponse(BaseModel):
    pack_id: str
    path: str
    content: str


class SkillPackValidationResponse(BaseModel):
    status: str
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SkillPackVersionResponse(BaseModel):
    id: str
    pack_id: str
    version: str
    manifest: dict[str, Any]
    validation: dict[str, Any]
    publish_note: str
    created_at: str | None = None


class SkillCreatorEventResponse(BaseModel):
    id: int
    session_id: str
    event_type: str
    payload: dict[str, Any]
    projection: dict[str, Any] = Field(default_factory=dict)
    created_at: str
```

Do not expose `snapshot_path` through the API response; it stays in backend state for prompt resolution.

- [x] **Step 4: Add resource conversion helper**

In `services/api/docagent_api/skill_packs.py`, add `add_text_resource` that mirrors `import_text_input` but writes under the pack draft root:

```text
resources/original/{group}/{stem}.txt
resources/markdown/{group}/{stem}.md
resources/reports/{group}/{stem}.json
```

Store `source_path`, `markdown_path`, and `conversion_report_path` as paths relative to the draft root. Return status `ready` when conversion succeeds. Defer binary upload routes; when they are introduced, they should return status `unsupported` with a conversion report that has `status: failed`.

- [x] **Step 5: Add routes and include them**

Create `services/api/docagent_api/routes/skill_packs.py` with:

```python
def create_skill_packs_router(state: DocAgentState) -> APIRouter:
    router = APIRouter()

    @router.get("/skill-packs", response_model=list[SkillPackSummaryResponse])
    def list_packs() -> list[dict[str, Any]]:
        return state.list_skill_packs()

    @router.post("/skill-packs", response_model=SkillPackSummaryResponse)
    def create_pack(request: CreateSkillPackRequest) -> dict[str, Any]:
        if not is_valid_pack_id(request.id):
            raise HTTPException(status_code=422, detail="Invalid pack id")
        if state.get_skill_pack(request.id) is not None:
            raise HTTPException(status_code=409, detail="Skill pack already exists")
        record = {"id": request.id, "title": request.title, "description": request.description, "draft_status": "draft"}
        state.save_skill_pack(record)
        return state.get_skill_pack(request.id)
```

Add the remaining endpoints with these behaviors:

- `GET /skill-packs/{pack_id}`: return 404 when `state.get_skill_pack(pack_id)` is missing.
- `POST /skill-packs/{pack_id}/resources/text`: require the pack, call `add_text_resource(state, pack_id, request.group, request.name, request.content)`, save the returned resource, and return `SkillPackResourceResponse`.
- `PUT /skill-packs/{pack_id}/artifacts`: require the pack, call `write_skill_pack_artifact(state, pack_id, request.path, request.content, "user", request.summary)`, and return `{"pack_id": pack_id, "path": request.path, "content": request.content}`. Convert `ValueError` from path validation into HTTP 400.
- `GET /skill-packs/{pack_id}/artifacts?path=SKILL.md`: require the pack, resolve the draft artifact path with the same path guard, return 404 if the file is missing, and return its content.
- `POST /skill-packs/{pack_id}/validate`: require the pack and return `validate_skill_pack_draft(state, pack_id)`.
- `POST /skill-packs/{pack_id}/publish`: require the pack, call `validate_skill_pack_draft`, reject blocking errors with HTTP 422, require every warning to be listed in `acknowledged_warnings`, then call `publish_skill_pack_snapshot`.

In `services/api/docagent_api/app.py`, include `create_skill_packs_router(state)`.

- [x] **Step 6: Run Task 3 verification**

Run:

```powershell
python -m pytest services/api/tests/test_skill_pack_routes.py services/api/tests/test_api.py::test_all_route_prefixes_respond_after_refactor -q
```

Expected: PASS.

- [x] **Step 7: Commit Task 3**

```powershell
git add services/api/docagent_api/request_models.py services/api/docagent_api/response_models.py services/api/docagent_api/routes/skill_packs.py services/api/docagent_api/app.py services/api/docagent_api/skill_packs.py services/api/tests/test_skill_pack_routes.py
git commit -m "feat: expose skill pack management routes"
```

## Task 4: Skill Creator Management Sessions And Mock Runtime Generation

**Files:**
- Modify: `services/api/docagent_api/app.py`
- Modify: `services/api/docagent_api/prompts.py`
- Modify: `services/api/docagent_api/request_models.py`
- Modify: `services/api/docagent_api/response_models.py`
- Modify: `services/api/docagent_api/routes/skill_packs.py`
- Modify: `services/api/docagent_api/skill_packs.py`
- Modify: `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py`
- Modify: `services/api/tests/test_prompts.py`
- Create: `services/api/tests/test_skill_creator_sessions.py`
- Modify: `agent/runtime-adapters/mock/tests/test_adapter.py`

- [x] **Step 1: Write failing Skill Creator session tests**

Create `services/api/tests/test_skill_creator_sessions.py`:

```python
from pathlib import Path

from fastapi.testclient import TestClient

from docagent_api.app import create_app


def _pack_with_resource(client: TestClient) -> None:
    client.post("/skill-packs", json={"id": "memo", "title": "Memo", "description": "Memo pack"})
    client.post("/skill-packs/memo/resources/text", json={
        "group": "examples",
        "name": "memo-example.txt",
        "content": "A useful memo starts with decision context, recommendation, and risk.",
    })


def test_skill_creator_generate_writes_artifacts_and_events(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))
    _pack_with_resource(client)

    session = client.post("/skill-packs/memo/skill-creator/sessions", json={
        "message": "Generate a memo skill from the uploaded material."
    }).json()
    assert session["session_scope"] == "pack-management"

    result = client.post(f"/skill-packs/memo/skill-creator/sessions/{session['id']}/generate", json={
        "message": "Generate the initial skill pack."
    })
    assert result.status_code == 200
    assert "SKILL.md" in result.json()["paths"]

    skill = client.get("/skill-packs/memo/artifacts", params={"path": "SKILL.md"}).json()
    assert "memo" in skill["content"].lower()

    events = client.get(f"/skill-packs/memo/skill-creator/sessions/{session['id']}/events").json()
    assert any(event["event_type"] == "file/write" for event in events)


def test_skill_creator_revision_reads_manual_edit(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))
    _pack_with_resource(client)
    session = client.post("/skill-packs/memo/skill-creator/sessions", json={"message": "Start"}).json()
    client.put("/skill-packs/memo/artifacts", json={
        "path": "SKILL.md",
        "content": "---\nname: memo\ndescription: Use for executive memos.\n---\n\n# Executive Memo\n\nPreserve this line.\n",
        "summary": "Manual edit",
    })

    response = client.post(f"/skill-packs/memo/skill-creator/sessions/{session['id']}/messages", json={
        "message": "Make the checklist stricter without removing my manual line."
    })

    assert response.status_code == 200
    skill = client.get("/skill-packs/memo/artifacts", params={"path": "SKILL.md"}).json()
    assert "Preserve this line." in skill["content"]
    events = client.get(f"/skill-packs/memo/skill-creator/sessions/{session['id']}/events").json()
    event_types = [event["event_type"] for event in events]
    assert "file/read" in event_types
    assert event_types.index("file/read") < event_types.index("file/write")
```

- [x] **Step 2: Run session tests and verify expected failure**

Run:

```powershell
python -m pytest services/api/tests/test_skill_creator_sessions.py -q
```

Expected: FAIL because Skill Creator session endpoints do not exist.

- [x] **Step 3: Add Skill Creator prompt bundle**

In `services/api/docagent_api/prompts.py`, add:

```python
SKILL_CREATOR_SYSTEM_PROMPT = """You are Skill Creator for DocAgent Workbench.
Create and revise document type skill packs from converted Markdown resources.
Do not build fixed workflows, content templates, or semantic RAG behavior.
Read current artifacts before revising them. Preserve intentional human edits.
Write concise SKILL.md guidance, checklist files, and resource notes."""


def build_skill_creator_prompt_bundle(
    pack_id: str,
    session_id: str,
    pack_workspace_root: Path,
    resource_manifest: dict[str, object],
    current_artifacts: dict[str, str],
    resource_budget_words: int = 6000,
) -> PromptBundle:
    budgeted_manifest = _budget_skill_creator_resources(resource_manifest, resource_budget_words)
    instruction = (
        f"Pack ID: {pack_id}\n"
        f"Session ID: {session_id}\n"
        f"Workspace root: {pack_workspace_root}\n"
        "Session scope: pack-management\n\n"
        "Resource manifest:\n"
        f"{json.dumps(budgeted_manifest, indent=2, ensure_ascii=False)}\n\n"
        "Current artifacts:\n"
        f"{json.dumps(current_artifacts, indent=2, ensure_ascii=False)}\n"
    )
    return PromptBundle(
        system_prompt=SKILL_CREATOR_SYSTEM_PROMPT,
        task_instruction=instruction,
        workspace_root=pack_workspace_root,
        doc_type_id="",
        pack_id=pack_id,
        metadata={"session_scope": "pack-management", "pack_id": pack_id, "session_id": session_id},
    )
```

Add `_budget_skill_creator_resources` in `prompts.py` with this minimum algorithm:

```python
GROUP_PRIORITY = {"specs": 0, "checklists": 1, "examples": 2, "export-references": 3}


def _budget_skill_creator_resources(resource_manifest: dict[str, object], budget_words: int) -> dict[str, object]:
    resources = list(resource_manifest.get("resources", []))
    budgeted: list[dict[str, object]] = []
    warnings: list[str] = []
    remaining = budget_words
    for resource in sorted(resources, key=lambda item: GROUP_PRIORITY.get(str(item.get("group")), 99)):
        copied = dict(resource)
        content = str(copied.get("markdown_excerpt") or copied.get("markdown") or "")
        words = content.split()
        if content and remaining <= 0:
            copied.pop("markdown", None)
            copied.pop("markdown_excerpt", None)
            warnings.append(f"Omitted {copied.get('id')} because Skill Creator context budget was exhausted")
        elif len(words) > remaining:
            copied.pop("markdown", None)
            copied["markdown_excerpt"] = " ".join(words[:remaining])
            warnings.append(f"Truncated {copied.get('id')} to fit Skill Creator context budget")
            remaining = 0
        else:
            if content:
                copied["markdown_excerpt"] = content
                copied.pop("markdown", None)
                remaining -= len(words)
        budgeted.append(copied)
    return {**resource_manifest, "resources": budgeted, "budget_warnings": warnings}
```

Add `services/api/tests/test_prompts.py` coverage that passes one spec resource and one long example resource, sets `budget_words=20`, and asserts `budget_warnings` contains a truncation warning and the returned manifest does not include full `markdown` bodies.

- [x] **Step 4: Add Skill Creator routes**

In `request_models.py`, add `SkillCreatorMessageRequest` with `message: str`.

In `response_models.py`, add `SkillCreatorSessionResponse` with `id`, `pack_id`, `session_scope`, `status`, `runtime`, and `runtime_session_id`. Add `SkillCreatorRunResponse` with `paths: list[str]`.

Change `create_skill_packs_router` to accept both `state` and `adapter`, and update `services/api/docagent_api/app.py` to include `create_skill_packs_router(state, adapter)`.

In `routes/skill_packs.py`, add:

- `POST /skill-packs/{pack_id}/skill-creator/sessions`
- `POST /skill-packs/{pack_id}/skill-creator/sessions/{session_id}/generate`
- `POST /skill-packs/{pack_id}/skill-creator/sessions/{session_id}/messages`
- `GET /skill-packs/{pack_id}/skill-creator/sessions/{session_id}/events`

Session creation should build the prompt bundle with `build_skill_creator_prompt_bundle`, call `adapter.create_session(session_id, prompt_bundle)`, persist a `skill_creator_sessions` row with `session_scope: pack-management` in the response, and persist runtime ACP updates into `skill_creator_events`.

- [x] **Step 5: Extend mock runtime for pack-management sessions**

In `MockRuntimeAdapter.create_session`, store:

```python
scope = str(prompt_bundle.metadata.get("session_scope", "authoring"))
record = {
    "session_scope": scope,
    "workspace_root": prompt_bundle.workspace_root,
    "state": RuntimeSessionState.IDLE,
}
if scope == "pack-management":
    record["pack_id"] = str(prompt_bundle.metadata["pack_id"])
else:
    record["task_id"] = str(prompt_bundle.metadata["task_id"])
self._sessions[session_id] = record
```

Preserve the existing authoring `task_id` metadata shape so current session and worker tests continue to pass.

In `MockRuntimeAdapter._run_prompt_action`, route management sessions:

```python
session = self._session(session_id)
if session.get("session_scope") == "pack-management":
    return self._run_skill_creator_action(session_id, prompt, metadata)
```

Add `_run_skill_creator_action` that writes:

- `SKILL.md`
- `checklists/quality.yaml`
- `notes/resources.md`

It must read existing `SKILL.md` and append revision notes without deleting existing manual lines. Return `RuntimeOperationResult` with `changed_paths` and `acp_updates` containing `message_delta`, `file/read`, `file/write`, and `message_completed`; the `file/read` update for `SKILL.md` must appear before the `file/write` update when revising existing artifacts.

- [x] **Step 6: Run Task 4 verification**

Run:

```powershell
python -m pytest services/api/tests/test_prompts.py services/api/tests/test_skill_creator_sessions.py agent/runtime-adapters/mock/tests/test_adapter.py -q
```

Expected: PASS.

- [x] **Step 7: Commit Task 4**

```powershell
git add services/api/docagent_api/app.py services/api/docagent_api/prompts.py services/api/docagent_api/request_models.py services/api/docagent_api/response_models.py services/api/docagent_api/routes/skill_packs.py services/api/docagent_api/skill_packs.py agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py services/api/tests/test_prompts.py services/api/tests/test_skill_creator_sessions.py agent/runtime-adapters/mock/tests/test_adapter.py
git commit -m "feat: add skill creator management sessions"
```

## Task 5: Authoring Tasks Bind To Published Pack Versions

**Files:**
- Modify: `services/api/docagent_api/request_models.py`
- Modify: `services/api/docagent_api/response_models.py`
- Modify: `services/api/docagent_api/routes/tasks.py`
- Modify: `services/api/docagent_api/prompts.py`
- Modify: `services/api/docagent_api/state.py`
- Modify: `services/api/tests/test_phase2_api.py`
- Create: `services/api/tests/test_authoring_pack_binding.py`
- Modify: `apps/web/src/types.ts`

- [x] **Step 1: Write failing binding tests**

Create `services/api/tests/test_authoring_pack_binding.py`:

```python
from pathlib import Path

from fastapi.testclient import TestClient

from docagent_api.app import create_app


def test_task_creation_binds_latest_published_pack_version(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))

    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Write a PRD"}).json()

    assert task["doc_type_id"] == "prd"
    assert task["pack_version_id"] == "prd-v001"


def test_task_creation_accepts_explicit_pack_version(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))
    client.post("/skill-packs", json={"id": "memo", "title": "Memo", "description": ""})
    client.put("/skill-packs/memo/artifacts", json={
        "path": "SKILL.md",
        "content": "---\nname: memo\ndescription: Use for memos.\n---\n\n# Memo\n",
        "summary": "Initial memo skill",
    })
    version = client.post("/skill-packs/memo/publish", json={"publish_note": "Memo v1"}).json()

    task = client.post("/tasks", json={
        "doc_type_id": "memo",
        "pack_version_id": version["id"],
        "brief": "Write a memo",
    }).json()

    assert task["pack_version_id"] == version["id"]


def test_task_creation_keeps_legacy_doc_type_fallback(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "doc-types" / "legacy").mkdir(parents=True)
    (repo / "doc-types" / "legacy" / "SKILL.md").write_text(
        "---\nname: legacy\ndescription: Legacy skill.\n---\n\n# Legacy\n",
        encoding="utf-8",
    )
    (repo / "agent" / "system-prompts").mkdir(parents=True)
    (repo / "agent" / "system-prompts" / "docagent-core.md").write_text("Core prompt\n", encoding="utf-8")
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=repo))

    response = client.post("/tasks", json={"doc_type_id": "legacy", "brief": "Use legacy pack"})

    assert response.status_code == 200
    assert response.json()["pack_version_id"] is None
```

- [x] **Step 2: Run binding tests and verify expected failure**

Run:

```powershell
python -m pytest services/api/tests/test_authoring_pack_binding.py -q
```

Expected: FAIL because `pack_version_id` is not accepted or returned.

- [x] **Step 3: Add request/response fields**

In `CreateTaskRequest`, add:

```python
pack_version_id: str | None = None
```

In `TaskResponse`, add:

```python
pack_version_id: str | None = None
```

In frontend `TaskRecord`, add:

```ts
pack_version_id?: string | null;
```

- [x] **Step 4: Resolve pack version during task creation**

In `routes/tasks.py`, replace the current `get_doc_type` validation with a published-pack-first lookup that keeps the legacy repo `doc-types` fallback:

```python
pack_version = state.get_skill_pack_version(request.pack_version_id) if request.pack_version_id else state.get_latest_skill_pack_version(request.doc_type_id)
legacy_doc_type = get_doc_type(root / "doc-types", request.doc_type_id) if pack_version is None else None
if pack_version is None and legacy_doc_type is None:
    raise HTTPException(status_code=404, detail="Published skill pack version not found")
```

Save `pack_version_id` on the task row when `pack_version` exists; save `None` when using the legacy fallback. This keeps repository `doc-types/*/SKILL.md` task creation working until all doc types are migrated into published pack versions.

Update `_task_row_to_dict` in `state.py` and every task response construction path so `pack_version_id` is returned for both newly-created tasks and fetched tasks.

- [x] **Step 5: Update prompt bundle resolution**

In `build_prompt_bundle`, accept `pack_version_id: str | None` and `skill_path: Path | None` after `doc_type_id`:

```python
def build_prompt_bundle(
    repo_root: Path,
    workspace_root: Path,
    task_id: str,
    session_id: str,
    doc_type_id: str,
    pack_version_id: str | None = None,
    skill_path: Path | None = None,
) -> PromptBundle:
    if not is_valid_doc_type_id(doc_type_id):
        raise ValueError("Invalid document type id")
    system_prompt_path = repo_root / "agent" / "system-prompts" / "docagent-core.md"
    resolved_skill_path = skill_path or repo_root / "doc-types" / doc_type_id / "SKILL.md"
```

Read `SKILL.md` from `resolved_skill_path`. Include `pack_version_id`, `session_scope: "authoring"`, and `skill_path: str(resolved_skill_path)` in metadata.

For authoring sessions, set `doc_type_id` to the task document type, set `pack_id` to `None`, and keep metadata scoped to authoring fields: `task_id`, `session_id`, `system_prompt_path`, `skill_path`, `pack_version_id`, and `session_scope`. Only Skill Creator management bundles set `pack_id`.

Update `routes/tasks.py` session creation:

```python
pack_version = state.get_skill_pack_version(task.get("pack_version_id"))
skill_path = Path(pack_version["snapshot_path"]) / "SKILL.md" if pack_version else None
prompt_bundle = build_prompt_bundle(
    root,
    Path(task["workspace_root"]),
    task["id"],
    session_id,
    task["doc_type_id"],
    task.get("pack_version_id"),
    skill_path,
)
```

Update `worker_tasks.py` `_create_runtime_session` with the same lookup so background workers rehydrate sessions from the immutable published snapshot. Keep `worker_tasks.py` authoring-only: if a loaded session dict ever has `session_scope == "pack-management"`, raise `RuntimeError("Pack-management sessions are not handled by authoring worker")` before reading `task_id`.

- [x] **Step 6: Run Task 5 verification**

Run:

```powershell
python -m pytest services/api/tests/test_authoring_pack_binding.py services/api/tests/test_phase2_api.py services/api/tests/test_worker_tasks.py -q
```

Expected: PASS.

- [x] **Step 7: Commit Task 5**

```powershell
git add services/api/docagent_api/request_models.py services/api/docagent_api/response_models.py services/api/docagent_api/routes/tasks.py services/api/docagent_api/prompts.py services/api/docagent_api/state.py services/api/tests/test_authoring_pack_binding.py services/api/tests/test_phase2_api.py services/api/tests/test_worker_tasks.py apps/web/src/types.ts
git commit -m "feat: bind authoring tasks to skill pack versions"
```

## Task 6: Frontend Pack Management In Settings Drawer

**Files:**
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/api.ts`
- Create: `apps/web/src/shell/state/useSkillPacks.ts`
- Create: `apps/web/src/shell/management/SkillPackManager.tsx`
- Modify: `apps/web/src/shell/SettingsDrawer.tsx`
- Modify: `apps/web/src/shell/theme/shell.css`
- Modify: `apps/web/src/shell/__tests__/AppShell.test.tsx`
- Modify: `apps/web/src/shell/__tests__/api.test.ts`

- [x] **Step 1: Write failing frontend API tests**

Add to `apps/web/src/shell/__tests__/api.test.ts`:

```ts
it("creates skill packs through the management API", async () => {
  const { api } = await import("../../api");
  await api.createSkillPack("memo", "Memo", "Executive memo pack");

  const [url, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit];
  expect(url).toContain("/skill-packs");
  expect(init.method).toBe("POST");
  expect(init.body).toBe(JSON.stringify({ id: "memo", title: "Memo", description: "Executive memo pack" }));
});

it("sends Skill Creator generate messages", async () => {
  const { api } = await import("../../api");
  await api.generateSkillPack("memo", "creator-session-1", "Generate the pack");

  const [url, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit];
  expect(url).toContain("/skill-packs/memo/skill-creator/sessions/creator-session-1/generate");
  expect(init.method).toBe("POST");
  expect(init.body).toBe(JSON.stringify({ message: "Generate the pack" }));
});
```

- [x] **Step 2: Run frontend API tests and verify expected failure**

Run:

```powershell
cd apps/web
npm run test:unit -- --run src/shell/__tests__/api.test.ts
```

Expected: FAIL because `createSkillPack` and `generateSkillPack` are not defined.

- [x] **Step 3: Add frontend types and API methods**

In `apps/web/src/types.ts`, add interfaces:

```ts
export interface SkillPackSummary {
  id: string;
  title: string;
  description: string;
  draft_status: string;
  latest_version_id?: string | null;
}

export interface SkillPackResource {
  id: string;
  pack_id: string;
  group: "examples" | "specs" | "checklists" | "export-references";
  original_filename: string;
  markdown_path?: string | null;
  conversion_report_path: string;
  status: "ready" | "warning" | "failed" | "unsupported";
  summary: string;
}

export interface SkillPackArtifact {
  pack_id: string;
  path: string;
  content: string;
}

export interface SkillPackVersion {
  id: string;
  pack_id: string;
  version: string;
  publish_note: string;
  manifest: Record<string, unknown>;
  validation: Record<string, unknown>;
  created_at?: string | null;
}

export interface SkillCreatorSession {
  id: string;
  pack_id: string;
  session_scope: "pack-management";
  status: string;
  runtime?: string | null;
  runtime_session_id?: string | null;
}

export interface SkillCreatorRunResult {
  paths: string[];
}

export interface SkillPackValidation {
  status: "passed" | "failed";
  errors: string[];
  warnings: string[];
}
```

In `apps/web/src/api.ts`, import the new types and add:

```ts
listSkillPacks: () => request<SkillPackSummary[]>("/skill-packs"),
createSkillPack: (id: string, title: string, description: string) =>
  request<SkillPackSummary>("/skill-packs", {
    method: "POST",
    body: JSON.stringify({ id, title, description }),
  }),
addSkillPackTextResource: (
  packId: string,
  group: SkillPackResource["group"],
  name: string,
  content: string,
) =>
  request<SkillPackResource>(`/skill-packs/${packId}/resources/text`, {
    method: "POST",
    body: JSON.stringify({ group, name, content }),
  }),
updateSkillPackArtifact: (packId: string, path: string, content: string, summary: string) =>
  request<SkillPackArtifact>(`/skill-packs/${packId}/artifacts`, {
    method: "PUT",
    body: JSON.stringify({ path, content, summary }),
  }),
getSkillPackArtifact: (packId: string, path: string) =>
  request<SkillPackArtifact>(`/skill-packs/${packId}/artifacts?path=${encodeURIComponent(path)}`),
createSkillCreatorSession: (packId: string, message: string) =>
  request<SkillCreatorSession>(`/skill-packs/${packId}/skill-creator/sessions`, {
    method: "POST",
    body: JSON.stringify({ message }),
  }),
generateSkillPack: (packId: string, sessionId: string, message: string) =>
  request<SkillCreatorRunResult>(`/skill-packs/${packId}/skill-creator/sessions/${sessionId}/generate`, {
    method: "POST",
    body: JSON.stringify({ message }),
  }),
sendSkillCreatorMessage: (packId: string, sessionId: string, message: string) =>
  request<SkillCreatorRunResult>(`/skill-packs/${packId}/skill-creator/sessions/${sessionId}/messages`, {
    method: "POST",
    body: JSON.stringify({ message }),
  }),
validateSkillPack: (packId: string) =>
  request<SkillPackValidation>(`/skill-packs/${packId}/validate`, { method: "POST" }),
publishSkillPack: (packId: string, publish_note: string, acknowledged_warnings: string[] = []) =>
  request<SkillPackVersion>(`/skill-packs/${packId}/publish`, {
    method: "POST",
    body: JSON.stringify({ publish_note, acknowledged_warnings }),
  }),
```

- [x] **Step 4: Add Query hooks**

Create `apps/web/src/shell/state/useSkillPacks.ts` with:

```ts
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api";
import type { SkillPackResource } from "../../types";

export function useSkillPacks() {
  return useQuery({ queryKey: ["skillPacks"], queryFn: () => api.listSkillPacks() });
}

export function useCreateSkillPack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, title, description }: { id: string; title: string; description: string }) =>
      api.createSkillPack(id, title, description),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["skillPacks"] }),
  });
}

export function useAddSkillPackTextResource(packId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ group, name, content }: { group: SkillPackResource["group"]; name: string; content: string }) => {
      if (!packId) throw new Error("Select a pack before adding resources");
      return api.addSkillPackTextResource(packId, group, name, content);
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["skillPacks"] }),
  });
}

export function useSkillPackArtifact(packId: string | null, path: string) {
  return useQuery({
    queryKey: ["skillPackArtifact", packId, path],
    queryFn: () => api.getSkillPackArtifact(packId ?? "", path),
    enabled: Boolean(packId),
  });
}

export function useUpdateSkillPackArtifact(packId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ path, content, summary }: { path: string; content: string; summary: string }) => {
      if (!packId) throw new Error("Select a pack before editing artifacts");
      return api.updateSkillPackArtifact(packId, path, content, summary);
    },
    onSuccess: (_result, variables) =>
      void queryClient.invalidateQueries({ queryKey: ["skillPackArtifact", packId, variables.path] }),
  });
}

export function useSkillCreatorGeneration(packId: string | null) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  useEffect(() => {
    setSessionId(null);
  }, [packId]);

  return useMutation({
    mutationFn: async (message: string) => {
      if (!packId) throw new Error("Select a pack before running Skill Creator");
      if (sessionId) {
        return api.sendSkillCreatorMessage(packId, sessionId, message);
      }
      const session = await api.createSkillCreatorSession(packId, message);
      setSessionId(session.id);
      return api.generateSkillPack(packId, session.id, message);
    },
  });
}

export function useValidateSkillPack(packId: string | null) {
  return useMutation({
    mutationFn: () => {
      if (!packId) throw new Error("Select a pack before validation");
      return api.validateSkillPack(packId);
    },
  });
}

export function usePublishSkillPack(packId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ note, warnings }: { note: string; warnings: string[] }) => {
      if (!packId) throw new Error("Select a pack before publishing");
      return api.publishSkillPack(packId, note, warnings);
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["skillPacks"] }),
  });
}
```

This keeps the MVP drawer as a continuing management conversation for the selected pack instead of creating an orphaned Skill Creator session on every Generate click.

- [x] **Step 5: Write failing management UI test**

In `AppShell.test.tsx`, extend the API mock with skill-pack methods. Add:

```tsx
it("creates a material-driven skill pack from the settings drawer", async () => {
  vi.mocked(api.listSkillPacks).mockResolvedValue([]);
  vi.mocked(api.createSkillPack).mockResolvedValue({
    id: "memo",
    title: "Memo",
    description: "Executive memo pack",
    draft_status: "draft",
    latest_version_id: null,
  });
  vi.mocked(api.addSkillPackTextResource).mockResolvedValue({
    id: "resource-1",
    pack_id: "memo",
    group: "examples",
    original_filename: "memo.txt",
    markdown_path: "resources/markdown/examples/memo.md",
    conversion_report_path: "resources/reports/examples/memo.json",
    status: "ready",
    summary: "",
  });

  renderAppShell("/?task=task-1&session=session-1");
  await userEvent.click(await screen.findByRole("button", { name: /open settings/i }));
  await userEvent.click(await screen.findByRole("button", { name: /new skill pack/i }));
  await userEvent.type(screen.getByLabelText("Pack id"), "memo");
  await userEvent.type(screen.getByLabelText("Pack title"), "Memo");
  await userEvent.type(screen.getByLabelText("Pack description"), "Executive memo pack");
  await userEvent.click(screen.getByRole("button", { name: "Create pack" }));

  await waitFor(() => expect(api.createSkillPack).toHaveBeenCalledWith("memo", "Memo", "Executive memo pack"));
});
```

- [x] **Step 6: Implement `SkillPackManager` and drawer integration**

Create `apps/web/src/shell/management/SkillPackManager.tsx` with:

- pack list;
- create pack form;
- resource text form with group select;
- Skill Creator message box and Generate button;
- `SKILL.md` textarea editor;
- validation and publish buttons.

Use compact controls and existing `Button`, `Input`, `Textarea`, and `Badge`. Keep sections un-nested and avoid card-in-card structure.

In `SettingsDrawer.tsx`, replace the existing drawer section headed `Skill Creator` with:

```tsx
<SkillPackManager />
```

- [x] **Step 7: Run Task 6 verification**

Run:

```powershell
cd apps/web
npm run test:unit -- --run src/shell/__tests__/api.test.ts src/shell/__tests__/AppShell.test.tsx
npm run test
```

Expected: PASS.

- [x] **Step 8: Commit Task 6**

```powershell
git add apps/web/src/types.ts apps/web/src/api.ts apps/web/src/shell/state/useSkillPacks.ts apps/web/src/shell/management/SkillPackManager.tsx apps/web/src/shell/SettingsDrawer.tsx apps/web/src/shell/theme/shell.css apps/web/src/shell/__tests__/AppShell.test.tsx apps/web/src/shell/__tests__/api.test.ts
git commit -m "feat: add skill pack management drawer"
```

## Task 7: Dedicated Management Route

**Files:**
- Modify: `apps/web/src/App.tsx`
- Create: `apps/web/src/shell/management/ManagementPage.tsx`
- Modify: `apps/web/src/shell/TopBar.tsx`
- Modify: `apps/web/src/shell/__tests__/AppShell.test.tsx`
- Create: `apps/web/src/shell/management/__tests__/ManagementPage.test.tsx`

- [x] **Step 1: Write failing route test**

Create `apps/web/src/shell/management/__tests__/ManagementPage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { createAppRouter } from "../../../App";
import { api } from "../../../api";

vi.mock("../../../api", () => ({
  api: {
    listSkillPacks: vi.fn().mockResolvedValue([]),
  },
}));

describe("ManagementPage", () => {
  it("renders the dedicated skill pack management route", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const router = createAppRouter(createMemoryHistory({ initialEntries: ["/management/skill-packs"] }));

    render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );

    expect(await screen.findByRole("heading", { name: "Skill Packs" })).toBeTruthy();
    expect(api.listSkillPacks).toHaveBeenCalled();
  });
});
```

- [x] **Step 2: Run route test and verify expected failure**

Run:

```powershell
cd apps/web
npm run test:unit -- --run src/shell/management/__tests__/ManagementPage.test.tsx
```

Expected: FAIL because `/management/skill-packs` does not exist.

- [x] **Step 3: Add route and page**

In `apps/web/src/App.tsx`, add:

```tsx
import { ManagementPage } from "./shell/management/ManagementPage";

export const managementRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/management/skill-packs",
  component: ManagementPage,
});

const routeTree = rootRoute.addChildren([indexRoute, managementRoute]);
```

Create `ManagementPage.tsx` that renders a full-width operational layout with heading `Skill Packs` and reuses `SkillPackManager`.

- [x] **Step 4: Add navigation entry**

In `TopBar.tsx`, add a compact icon+text button or link labelled `Skill Packs` that navigates to `/management/skill-packs`. Keep the existing settings button because runtime and document type read-only details still live there during the transition.

- [x] **Step 5: Run Task 7 verification**

Run:

```powershell
cd apps/web
npm run test:unit -- --run src/shell/management/__tests__/ManagementPage.test.tsx src/shell/__tests__/AppShell.test.tsx
npm run test
```

Expected: PASS.

- [x] **Step 6: Commit Task 7**

```powershell
git add apps/web/src/App.tsx apps/web/src/shell/TopBar.tsx apps/web/src/shell/management/ManagementPage.tsx apps/web/src/shell/management/__tests__/ManagementPage.test.tsx
git commit -m "feat: add skill pack management route"
```

## Task 8: Full Verification And Documentation Sync

**Files:**
- Modify: `README.md`
- Modify: `docs/product/ui-surfaces.md`
- Modify: `docs/architecture/agent-runtime.md`
- Modify: `docs/superpowers/plans/2026-05-17-skill-creator-versioned-packs.md`

- [x] **Step 1: Update docs with the new product facts**

Update `README.md` current implementation notes to say skill packs are versioned product objects with draft and published states.

Update `docs/product/ui-surfaces.md` to replace future-tense Skill Creator wording with the implemented MVP shape:

- material upload/paste;
- generated artifacts;
- validation;
- publish/version;
- dedicated route after drawer entry.

Update `docs/architecture/agent-runtime.md` to state that authoring sessions use `session_scope = authoring` and Skill Creator sessions use `session_scope = pack-management`.

- [x] **Step 2: Run backend verification**

Run:

```powershell
python -m pytest packages/contracts/tests services/api/tests agent/runtime-adapters/mock/tests -q
```

Expected: PASS.

- [x] **Step 3: Run frontend verification**

Run:

```powershell
cd apps/web
npm run test:unit -- --run
npm run test
npm run build
```

Expected: PASS. `npm run build` may still emit the existing Vite large-chunk warning; no TypeScript errors are acceptable.

- [x] **Step 4: Run documentation structure check**

Run:

```powershell
Get-ChildItem -Recurse -File | Select-Object FullName | Out-Null
```

Expected: exit code 0.

- [x] **Step 5: Search for stale stubs and old assumptions**

Run:

```powershell
rg -n "Phase 2 place[h]older retained|manual SKILL[.]md editor|doc_type_id only" README.md docs services apps packages -S
```

Expected: no matches except historical completed plans or quoted review material. If historical matches appear under `docs/*/completed`, leave them unchanged.

- [x] **Step 6: Mark this plan complete and commit**

Move this file to `docs/superpowers/completed/2026-05-17-skill-creator-versioned-packs.md`, preserving all completed checkboxes.

Run:

```powershell
git add README.md docs/product/ui-surfaces.md docs/architecture/agent-runtime.md docs/superpowers/plans/2026-05-17-skill-creator-versioned-packs.md docs/superpowers/completed/2026-05-17-skill-creator-versioned-packs.md
git commit -m "docs: complete skill creator versioned packs plan"
```

## Execution Notes

- Keep each task as a separate commit.
- Keep authoring task/session behavior passing after every backend task.
- Do not let authoring tasks read draft pack files.
- Do not add binary import support beyond unsupported conversion reports in this plan.
- Prefer synchronous Skill Creator operations in the first pass; background execution can reuse the same route shape after the MVP is stable.
- If a route or UI test requires a large fixture, reduce the fixture to one short text resource and one generated `SKILL.md`.

## Review Fixes - 2026-05-17

Claude review identified release-hardening gaps after the MVP implementation. The follow-up fix added regression coverage and addressed:

- publish rollback when DB version save fails;
- idempotent version replay without regressing `latest_version_id`;
- database uniqueness for `(pack_id, version)` via ORM metadata and Alembic `0005`;
- Skill Creator session rollback when runtime session creation fails;
- reuse of publish validation from the route to avoid a double-read race;
- seed bootstrap traceback logging;
- removal of the dead pack-management guard in the authoring worker.

Verification:

```powershell
python -m pytest services/api/tests/test_skill_packs.py::test_publish_snapshot_cleans_partial_directory_when_db_save_fails services/api/tests/test_skill_pack_state.py::test_replaying_existing_skill_pack_version_does_not_regress_latest services/api/tests/test_skill_pack_state.py::test_skill_pack_versions_are_unique_per_pack_and_version services/api/tests/test_skill_creator_sessions.py::test_skill_creator_session_create_failure_removes_session -q
python -m pytest services/api/tests/test_skill_packs.py services/api/tests/test_skill_pack_state.py services/api/tests/test_skill_creator_sessions.py services/api/tests/test_worker_tasks.py services/api/tests/test_phase3_api.py -q
python -m pytest packages/contracts/tests services/api/tests agent/runtime-adapters/mock/tests -q
git diff --check -- . ':!.claude/settings.local.json'
```
