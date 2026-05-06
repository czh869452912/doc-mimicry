# Phase 2 Review Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Fix the confirmed Phase 2 code review issues before Phase 3 planning begins.

**Architecture:** Keep the Phase 2 authoring loop API-first and preserve the runtime adapter boundary. This cleanup tightens session state contracts, endpoint error handling, timestamp generation, checkpoint event paths, timeline event identity, and development dependency metadata without adding new user-facing features.

**Tech Stack:** Python 3.11, FastAPI, pytest, TypedDict contracts, local filesystem state, mock runtime adapter.

---

## Scope

- Fix review findings C1, C2, and I1-I5 from `docs/reviews/active/code-review-phase2.md`.
- Add focused regression tests for the broken paths.
- Record minor review findings as Phase 3 known debt instead of expanding this cleanup into UI or concurrency work.
- Move the completed Phase 2 implementation plan out of `active/` after this cleanup verifies.

## Non-goals

- Do not implement Phase 3 features.
- Do not redesign the authoring loop UI.
- Do not replace file-backed state or introduce database locking.
- Do not add a full Markdown renderer in this cleanup.
- Do not build duplicate-name import policy unless it becomes necessary for a failing test in this plan.

## Files And Responsibilities

- `services/api/docagent_api/models.py`: session status contract.
- `services/api/docagent_api/time.py`: shared UTC timestamp helper for API records.
- `services/api/docagent_api/app.py`: endpoint error mapping and API timestamp usage.
- `services/api/tests/test_phase2_api.py`: API regressions for Phase 2 states and revision errors.
- `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py`: runtime timestamp usage, unique event ids, revision validation, and checkpoint path correctness.
- `agent/runtime-adapters/mock/tests/test_authoring_loop.py`: adapter regressions for duplicate event ids, missing selected text, and checkpoint paths.
- `packages/workspace/docagent_workspace/checkpoint.py`: real default checkpoint timestamps.
- `packages/workspace/tests/test_checkpoint.py`: checkpoint timestamp regression.
- `pyproject.toml`: development test dependencies.
- `docs/exec-plans/active/2026-04-30-phase-2-authoring-loop.md`: already marked complete; move to `completed/` in Task 7.
- `docs/exec-plans/active/2026-05-06-phase-2-review-cleanup.md`: track this cleanup and known Phase 3 debt.

## Task 1: Session Status Contract And Missing Draft Error

**Files:**
- Modify: `services/api/docagent_api/models.py`
- Modify: `services/api/docagent_api/app.py`
- Test: `services/api/tests/test_phase2_api.py`

- [x] **Step 1: Add failing API regression tests**

Add these tests to `services/api/tests/test_phase2_api.py`:

```python
def test_phase2_session_statuses_are_persisted(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build onboarding analytics"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    start_response = client.post(f"/sessions/{session['id']}/loop/start")
    assert start_response.status_code == 200
    assert client.get(f"/sessions/{session['id']}").json()["status"] == "await_outline_approval"

    outline = client.get(f"/tasks/{task['id']}/workspace/files", params={"path": "draft/outline.md"}).json()
    approve_response = client.post(
        f"/sessions/{session['id']}/outline/approve",
        json={"outline_markdown": outline["content"]},
    )

    assert approve_response.status_code == 200
    assert client.get(f"/sessions/{session['id']}").json()["status"] == "draft_ready"


def test_revise_selection_before_draft_returns_400(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build onboarding analytics"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    response = client.post(
        f"/sessions/{session['id']}/revision/selection",
        json={"selected_text": "Build onboarding analytics", "instruction": "Make it sharper"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Draft does not exist. Approve the outline first."
```

- [x] **Step 2: Run the focused API tests**

Run:

```powershell
python -m pytest services/api/tests/test_phase2_api.py::test_phase2_session_statuses_are_persisted services/api/tests/test_phase2_api.py::test_revise_selection_before_draft_returns_400 -q
```

Expected: the missing-draft test fails with an unhandled server error before implementation.

- [x] **Step 3: Extend the status Literal**

Modify `SessionRecord` in `services/api/docagent_api/models.py`:

```python
class SessionRecord(TypedDict):
    id: str
    task_id: str
    status: Literal["idle", "running", "paused", "await_outline_approval", "draft_ready", "completed", "failed"]
    created_at: str
    updated_at: str
```

- [x] **Step 4: Add only the missing-draft try/except block**

`_event_paths(events)` already exists and the endpoint already returns it. Keep the existing successful return line unchanged. Only wrap the `adapter.revise_selection(...)` call in `services/api/docagent_api/app.py`:

```python
        try:
            events = adapter.revise_selection(
                task_id=task["id"],
                session_id=session_id,
                workspace_root=Path(task["workspace_root"]),
                selected_text=request.selected_text,
                instruction=request.instruction,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=400, detail="Draft does not exist. Approve the outline first.") from exc
```

- [x] **Step 5: Re-run the focused API tests**

Run:

```powershell
python -m pytest services/api/tests/test_phase2_api.py::test_phase2_session_statuses_are_persisted services/api/tests/test_phase2_api.py::test_revise_selection_before_draft_returns_400 -q
```

Expected: PASS.

- [x] **Step 6: Commit Task 1**

Run:

```powershell
git add services/api/docagent_api/models.py services/api/docagent_api/app.py services/api/tests/test_phase2_api.py
git commit -m "Fix Phase 2 session status and missing draft error"
```

## Task 2: Shared UTC Timestamps

**Files:**
- Create: `services/api/docagent_api/time.py`
- Modify: `services/api/docagent_api/app.py`
- Modify: `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py`
- Modify: `packages/workspace/docagent_workspace/checkpoint.py`
- Test: `packages/workspace/tests/test_checkpoint.py`

- [x] **Step 1: Add checkpoint timestamp regression**

Add this test to `packages/workspace/tests/test_checkpoint.py`:

```python
def test_checkpoint_default_created_at_is_current_utc_timestamp(tmp_path: Path):
    root = tmp_path / "task-001"
    create_workspace(root, brief="Write a PRD.")
    (root / "draft" / "draft.md").write_text("# Draft\n", encoding="utf-8")

    version = checkpoint_draft(root, summary="Initial draft")

    assert version.created_at.endswith("Z")
    assert version.created_at != "1970-01-01T00:00:00Z"
```

- [x] **Step 2: Run the checkpoint timestamp test**

Run:

```powershell
python -m pytest packages/workspace/tests/test_checkpoint.py::test_checkpoint_default_created_at_is_current_utc_timestamp -q
```

Expected: FAIL because the default timestamp is the epoch.

- [x] **Step 3: Add API timestamp helper**

Create `services/api/docagent_api/time.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
```

- [x] **Step 4: Update API timestamp assignments**

In `services/api/docagent_api/app.py`, import `utc_now`:

```python
from docagent_api.time import utc_now
```

Replace each hardcoded `"2026-04-30T00:00:00Z"` assignment in `create_task`, `create_session`, `add_text_input`, and `_manual_event` with `utc_now()`. For records with both `created_at` and `updated_at`, assign once and reuse:

```python
created_at = utc_now()
record = {
    "created_at": created_at,
    "updated_at": created_at,
}
```

- [x] **Step 5: Update adapter timestamp helper**

In `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py`, add these imports once near the top:

```python
from datetime import datetime, timezone
from uuid import uuid4
```

Add a local helper:

```python
def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
```

Use `_utc_now()` for all `SemanticTimelineEvent.created_at` values. `uuid4` is imported in this step for Task 4; do not add the same import again later.

- [x] **Step 6: Update checkpoint default timestamp**

In `packages/workspace/docagent_workspace/checkpoint.py`, add:

```python
from datetime import datetime, timezone


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
```

Change the function signature and body:

```python
def checkpoint_draft(root: Path, summary: str, created_at: str | None = None) -> DraftVersion:
    ...
    return DraftVersion(
        ...
        created_at=created_at or _utc_now(),
    )
```

- [x] **Step 7: Run timestamp-related tests**

Run:

```powershell
python -m pytest packages/workspace/tests/test_checkpoint.py services/api/tests/test_imports.py services/api/tests/test_phase2_api.py agent/runtime-adapters/mock/tests -q
```

Expected: PASS.

- [x] **Step 8: Commit Task 2**

Run:

```powershell
git add services/api/docagent_api/time.py services/api/docagent_api/app.py agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py packages/workspace/docagent_workspace/checkpoint.py packages/workspace/tests/test_checkpoint.py
git commit -m "Use real UTC timestamps in Phase 2 records"
```

## Task 3: Selection Revision Validation

**Files:**
- Modify: `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py`
- Modify: `services/api/docagent_api/app.py`
- Test: `agent/runtime-adapters/mock/tests/test_authoring_loop.py`
- Test: `services/api/tests/test_phase2_api.py`

- [x] **Step 1: Add failing adapter test for missing selected text**

Add to `agent/runtime-adapters/mock/tests/test_authoring_loop.py`:

```python
import pytest


def test_revise_selection_raises_when_selected_text_is_missing(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "draft").mkdir(parents=True)
    (workspace / "draft" / "draft.md").write_text("# PRD Draft\n\nOld passage\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()

    with pytest.raises(ValueError, match="Selected text not found in draft"):
        adapter.revise_selection(
            "task-001",
            "session-001",
            workspace,
            selected_text="Missing passage",
            instruction="Make it sharper",
        )
```

- [x] **Step 2: Add failing API test for missing selected text**

Add to `services/api/tests/test_phase2_api.py`:

```python
def test_revise_selection_missing_text_returns_422(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build onboarding analytics"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    client.post(f"/sessions/{session['id']}/loop/start")
    outline = client.get(f"/tasks/{task['id']}/workspace/files", params={"path": "draft/outline.md"}).json()
    client.post(f"/sessions/{session['id']}/outline/approve", json={"outline_markdown": outline["content"]})

    response = client.post(
        f"/sessions/{session['id']}/revision/selection",
        json={"selected_text": "Not in draft", "instruction": "Make it sharper"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Selected text not found in draft."
```

- [x] **Step 3: Run the focused tests**

Run:

```powershell
python -m pytest agent/runtime-adapters/mock/tests/test_authoring_loop.py::test_revise_selection_raises_when_selected_text_is_missing services/api/tests/test_phase2_api.py::test_revise_selection_missing_text_returns_422 -q
```

Expected: FAIL before implementation.

- [x] **Step 4: Validate selected text in the adapter**

Modify `revise_selection` in `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py`:

```python
        if selected_text not in current:
            raise ValueError("Selected text not found in draft")
        replacement = f"Revised passage: {instruction}"
        draft_path.write_text(current.replace(selected_text, replacement, 1), encoding="utf-8")
```

- [x] **Step 5: Map validation error to 422**

Extend the `try` block in the API `revise_selection` endpoint:

```python
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Selected text not found in draft.") from exc
```

- [x] **Step 6: Re-run focused tests**

Run:

```powershell
python -m pytest agent/runtime-adapters/mock/tests/test_authoring_loop.py::test_revise_selection_raises_when_selected_text_is_missing services/api/tests/test_phase2_api.py::test_revise_selection_missing_text_returns_422 -q
```

Expected: PASS.

- [x] **Step 7: Commit Task 3**

Run:

```powershell
git add agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py services/api/docagent_api/app.py agent/runtime-adapters/mock/tests/test_authoring_loop.py services/api/tests/test_phase2_api.py
git commit -m "Reject missing selected draft text"
```

## Task 4: Unique Event IDs And Actual Checkpoint Paths

**Files:**
- Modify: `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py`
- Test: `agent/runtime-adapters/mock/tests/test_authoring_loop.py`
- Test: `agent/runtime-adapters/mock/tests/test_adapter.py`

- [x] **Step 1: Add failing event id uniqueness test**

Add to `agent/runtime-adapters/mock/tests/test_authoring_loop.py`:

```python
def test_repeated_outline_builds_emit_unique_event_ids(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "brief.md").write_text("Build a PRD for onboarding analytics\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()
    first_events = adapter.build_context_and_outline("task-001", "session-001", workspace)
    second_events = adapter.build_context_and_outline("task-001", "session-001", workspace)

    event_ids = [event.id for event in first_events + second_events]
    assert len(event_ids) == len(set(event_ids))
```

- [x] **Step 2: Add failing checkpoint path test**

Add to `agent/runtime-adapters/mock/tests/test_adapter.py`:

```python
def test_later_message_checkpoint_event_uses_actual_version_path(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "draft").mkdir(parents=True)
    (workspace / "draft" / "draft.md").write_text("# Existing\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()
    adapter.send_message(
        task_id="task-001",
        session_id="session-001",
        workspace_root=workspace,
        message="First revision",
    )
    events = adapter.send_message(
        task_id="task-001",
        session_id="session-001",
        workspace_root=workspace,
        message="Second revision",
    )

    checkpoint_events = [event for event in events if event.kind.value == "create_checkpoint"]
    assert checkpoint_events[0].paths == ["versions/v002.md"]
```

- [x] **Step 3: Run the focused tests**

Run:

```powershell
python -m pytest agent/runtime-adapters/mock/tests/test_authoring_loop.py::test_repeated_outline_builds_emit_unique_event_ids agent/runtime-adapters/mock/tests/test_adapter.py::test_later_message_checkpoint_event_uses_actual_version_path -q
```

Expected: FAIL before implementation.

- [x] **Step 4: Make `_event` ids unique**

Modify `_event` in `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py`. `uuid4` was imported in Task 2; do not add a duplicate import:

```python
        id=f"{session_id}-{suffix}-{uuid4().hex[:8]}",
```

- [x] **Step 5: Use actual checkpoint path in `_revise`**

Modify `_revise`:

```python
        checkpoint = checkpoint_draft(workspace_root, summary=f"Before revision: {message}")
        ...
            _event(
                task_id,
                session_id,
                "checkpoint-1",
                TimelineActor.SYSTEM,
                SemanticEventKind.CREATE_CHECKPOINT,
                "Create checkpoint",
                [checkpoint.version_path],
            ),
```

- [x] **Step 6: Re-run adapter tests**

Run:

```powershell
python -m pytest agent/runtime-adapters/mock/tests -q
```

Expected: PASS.

- [x] **Step 7: Commit Task 4**

Run:

```powershell
git add agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py agent/runtime-adapters/mock/tests/test_authoring_loop.py agent/runtime-adapters/mock/tests/test_adapter.py
git commit -m "Make mock runtime events and checkpoints traceable"
```

## Task 5: Development Dependencies

**Files:**
- Modify: `pyproject.toml`

- [x] **Step 1: Add dev optional dependency group**

Add to `pyproject.toml`:

```toml
[project.optional-dependencies]
dev = [
  "pytest",
  "httpx",
]
```

- [x] **Step 2: Verify project metadata remains parseable**

Run:

```powershell
python -m pip install -e ".[dev]"
```

Expected: package metadata resolves and dev dependencies are available.

- [x] **Step 3: Commit Task 5**

Run:

```powershell
git add pyproject.toml
git commit -m "Declare test development dependencies"
```

## Task 6: Record Minor Debt

**Files:**
- Modify: `docs/exec-plans/active/2026-05-06-phase-2-review-cleanup.md`

- [x] **Step 1: Confirm Phase 2 cleanup dependency note exists**

This is already complete in `docs/exec-plans/active/2026-04-30-phase-2-authoring-loop.md`:

```markdown
**Post-review cleanup:** Before Phase 3 planning, complete `docs/exec-plans/active/2026-05-06-phase-2-review-cleanup.md`.
```

- [x] **Step 2: Keep minor review findings as known Phase 3 debt**

Keep one actual `Known Phase 3 Debt From Review` section in the current cleanup plan. The authoritative section is below Task 7.

- [x] **Step 3: Commit Task 6**

Run:

```powershell
git add docs/exec-plans/active/2026-05-06-phase-2-review-cleanup.md
git commit -m "Record Phase 3 cleanup debt"
```

## Task 7: Final Verification And Phase 2 Plan Archival

**Files:**
- Move: `docs/exec-plans/active/2026-04-30-phase-2-authoring-loop.md` to `docs/exec-plans/completed/2026-04-30-phase-2-authoring-loop.md`
- Modify: `docs/exec-plans/active/2026-05-06-phase-2-review-cleanup.md`

- [x] **Step 1: Run focused backend/runtime verification**

Run:

```powershell
python -m pytest services/api/tests/test_phase2_api.py agent/runtime-adapters/mock/tests packages/workspace/tests packages/contracts/tests -q
```

Expected: PASS.

- [x] **Step 2: Run full Python verification**

Run:

```powershell
python -m pytest packages/contracts/tests packages/workspace/tests packages/timeline/tests tools/import/tests services/api/tests agent/runtime-adapters/mock/tests tests -q
```

Expected: PASS.

- [x] **Step 3: Archive the completed Phase 2 implementation plan**

Run:

```powershell
Move-Item -LiteralPath docs/exec-plans/active/2026-04-30-phase-2-authoring-loop.md -Destination docs/exec-plans/completed/2026-04-30-phase-2-authoring-loop.md
```

- [x] **Step 4: Run documentation structure check**

Run:

```powershell
Get-ChildItem -Recurse -File | Select-Object FullName
```

Expected: output includes `docs/exec-plans/completed/2026-04-30-phase-2-authoring-loop.md` and `docs/exec-plans/active/2026-05-06-phase-2-review-cleanup.md`.

- [x] **Step 5: Commit Task 7**

Run:

```powershell
git add docs/exec-plans/active/2026-05-06-phase-2-review-cleanup.md docs/exec-plans/completed/2026-04-30-phase-2-authoring-loop.md
git add -u docs/exec-plans/active/2026-04-30-phase-2-authoring-loop.md
git commit -m "Verify cleanup and archive Phase 2 plan"
```

## Known Phase 3 Debt From Review

- M1: Export `InputPaths`, `ContextPaths`, `DraftPaths`, `ReviewPaths`, and `LogPaths` from `packages/contracts/docagent_contracts/__init__.py` if external callers need direct imports.
- M2: Define duplicate import filename policy for `import_text_input`; current behavior overwrites same-stem files.
- M4: Replace raw paragraph preview in `WorkbenchPage` with Markdown rendering.
- M5: Add file locking or a stronger state backend before multi-worker deployment.
- M6: Replace default brief placeholder text with safer empty or sample-selection behavior.

## Verification Commands

Primary execution uses Task 7. For documentation-only edits to this plan, run:

```powershell
Get-ChildItem -Recurse -File | Select-Object FullName
```

## Rollback Or Recovery Notes

- The code changes are isolated to contracts, API error handling, mock runtime behavior, checkpoint metadata, and dependency metadata.
- If timestamp changes break deterministic assertions, update tests to assert timestamp shape and non-placeholder behavior rather than exact values.
- If unique event ids break UI keys, keep rendering by `event.id` and remove any reliance on suffix-only ids.
- If endpoint error mapping changes client behavior, preserve the response text in this plan so UI status messages remain predictable.
- If the final verification fails, keep the Phase 2 plan in `active/` until the failure is fixed and Task 7 passes.

## Open Questions

- Should M1 be promoted into this cleanup because it is a low-risk contract export change, or should it wait until an external caller needs direct sub-dataclass imports?
- Should duplicate input names be rejected, versioned, or overwritten in Phase 3?
- Should `utc_now()` live in a shared package later so contracts, workspace helpers, API, and runtime adapters do not duplicate timestamp formatting?
