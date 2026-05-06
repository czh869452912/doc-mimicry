# Phase 3 OpenHands Runtime Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the product's direct mock-runtime dependency with a formal runtime adapter boundary and add OpenHands as the first real runtime implementation.

**Execution readiness:** Phase 3 runtime adapter tests, full Python verification, and frontend build pass locally.

**Architecture:** Keep `services/api` runtime-agnostic. Define product-level runtime contracts in `packages/contracts`, choose adapters through a backend factory, keep mock as the deterministic test/runtime fallback, and isolate all OpenHands-specific SDK or HTTP details under `agent/runtime-adapters/openhands`. OpenHands event streaming is consumed server-side first; the UI continues polling existing session and timeline endpoints.

**Tech Stack:** Python 3.11, FastAPI, pytest, dataclasses/Protocols, file-backed JSON/JSONL state, optional OpenHands Agent Server / SDK integration.

---

## Context

Design source:

```text
docs/superpowers/specs/2026-05-06-openhands-runtime-adapter-design.md
```

OpenHands references checked during planning:

- `https://docs.openhands.dev/sdk/arch/agent-server`
- `https://docs.openhands.dev/sdk/guides/agent-server/overview`
- `https://docs.openhands.dev/sdk/guides/agent-server/local-server`

The current backend imports `MockRuntimeAdapter` directly in `services/api/docagent_api/app.py`. This plan removes that coupling while preserving the existing Phase 2 API behavior.

## Scope

- Add shared runtime contract dataclasses and a runtime adapter `Protocol`.
- Move timestamp formatting to a shared utility.
- Add raw runtime event JSONL storage.
- Add a stable session state transition helper.
- Add prompt assembly in the product backend.
- Move mock behind the formal adapter contract.
- Add runtime adapter factory and backend configuration.
- Add OpenHands adapter package with a fake-client-tested first slice.
- Add raw-event to semantic-event mapping for OpenHands-like events.
- Add `cancel` endpoint and timeout/cancellation contract.
- Add documentation and opt-in OpenHands smoke test path.

## Non-Goals

- Do not build a custom agent loop.
- Do not build custom sandbox, tool, permission, or runtime orchestration systems.
- Do not add a Responses API tool-loop adapter.
- Do not replace the file-backed state backend.
- Do not change the React UI to WebSocket/SSE streaming.
- Do not require real OpenHands in normal CI.

## Files And Responsibilities

- `packages/contracts/docagent_contracts/runtime.py`: runtime-facing dataclasses, session states, adapter protocol.
- `packages/contracts/docagent_contracts/time.py`: shared UTC timestamp helper.
- `packages/contracts/docagent_contracts/__init__.py`: exports runtime contracts and `utc_now`.
- `packages/contracts/tests/test_runtime_contracts.py`: runtime contract and timestamp tests.
- `services/api/docagent_api/session_state.py`: allowed state transitions and invalid-operation errors.
- `services/api/tests/test_session_state.py`: transition tests.
- `services/api/docagent_api/prompts.py`: prompt bundle assembly from repo files and task workspace metadata.
- `services/api/tests/test_prompts.py`: prompt assembly tests.
- `services/api/docagent_api/state.py`: raw runtime event JSONL persistence.
- `services/api/tests/test_state.py`: raw event persistence tests.
- `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py`: implements formal runtime interface.
- `agent/runtime-adapters/openhands/docagent_openhands_runtime/__init__.py`: OpenHands adapter package export.
- `agent/runtime-adapters/openhands/docagent_openhands_runtime/client.py`: small client protocol and SDK-backed client wrapper.
- `agent/runtime-adapters/openhands/docagent_openhands_runtime/adapter.py`: OpenHands adapter implementation.
- `agent/runtime-adapters/openhands/tests/test_adapter.py`: fake-client OpenHands adapter tests.
- `packages/timeline/docagent_timeline/openhands_mapper.py`: raw OpenHands-like event to semantic event mapper.
- `packages/timeline/tests/test_openhands_mapper.py`: mapper tests.
- `services/api/docagent_api/runtime_factory.py`: runtime selection from config/env.
- `services/api/docagent_api/app.py`: injects factory-selected adapter, enforces state transitions, appends raw events.
- `services/api/tests/test_runtime_factory.py`: factory tests.
- `services/api/tests/test_phase3_api.py`: API-level state-machine and runtime selection tests.
- `agent/runtime-adapters/README.md`: documents adapter contract and runtime choice.
- `services/api/README.md`: documents `DOCAGENT_RUNTIME` and OpenHands env vars.
- `docs/quality/testing.md`: adds Phase 3 verification and opt-in smoke commands.
- `tools/runtime/openhands_smoke.py`: opt-in smoke runner against a configured OpenHands server.

## Verification Commands

Run after implementation:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest packages/contracts/tests packages/workspace/tests packages/timeline/tests tools/import/tests services/api/tests agent/runtime-adapters/mock/tests agent/runtime-adapters/openhands/tests tests -q
cd apps/web
npm run build
```

Expected:

```text
all Python tests pass
frontend build succeeds
```

Opt-in OpenHands smoke, only when OpenHands Agent Server is configured:

```powershell
$env:DOCAGENT_RUNTIME = "openhands"
$env:OPENHANDS_BASE_URL = "http://127.0.0.1:8001"
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tools/runtime/openhands_smoke.py
```

Expected:

```text
created task
created session
started loop
approved outline
revised selection
ran checklist
exported markdown
ok
```

## Rollback Or Recovery

- If OpenHands local setup is unstable, keep `DOCAGENT_RUNTIME=mock` as default and complete the contract/factory/state tasks first.
- If OpenHands SDK APIs differ from the docs, update only `agent/runtime-adapters/openhands/docagent_openhands_runtime/client.py`; do not leak SDK types into `services/api`.
- If raw event volume becomes large, keep JSONL and add truncation/rotation later; do not embed raw payloads in semantic timeline JSON.
- If state transitions block a legitimate Phase 2 flow, adjust `session_state.py` and tests rather than bypassing checks in endpoints.

---

## Task 1: Shared Runtime Contracts And Time Utility

**Files:**
- Create: `packages/contracts/docagent_contracts/runtime.py`
- Create: `packages/contracts/docagent_contracts/time.py`
- Modify: `packages/contracts/docagent_contracts/__init__.py`
- Modify: `pyproject.toml`
- Test: `packages/contracts/tests/test_runtime_contracts.py`

- [ ] **Step 1: Write failing runtime contract tests**

Create `packages/contracts/tests/test_runtime_contracts.py`:

```python
from dataclasses import asdict

from docagent_contracts import (
    PromptBundle,
    RawRuntimeEvent,
    RuntimeAdapter,
    RuntimeKind,
    RuntimeOperationResult,
    RuntimeSessionState,
    utc_now,
)


def test_runtime_operation_result_shape() -> None:
    result = RuntimeOperationResult(
        session_id="session-001",
        next_state=RuntimeSessionState.DRAFT_READY,
        events=[],
        changed_paths=["draft/draft.md"],
        raw_events=[],
    )

    assert result.session_id == "session-001"
    assert result.next_state is RuntimeSessionState.DRAFT_READY
    assert result.changed_paths == ["draft/draft.md"]


def test_prompt_bundle_is_serializable() -> None:
    bundle = PromptBundle(
        system_prompt="core",
        task_instruction="write",
        workspace_root="workspace/task-001",
        doc_type_id="prd",
        metadata={"task_id": "task-001"},
    )

    assert asdict(bundle)["metadata"]["task_id"] == "task-001"


def test_raw_runtime_event_shape() -> None:
    event = RawRuntimeEvent(
        id="raw-001",
        session_id="session-001",
        runtime=RuntimeKind.OPENHANDS,
        runtime_session_id="oh-001",
        kind="message",
        payload={"content": "hello"},
        created_at="2026-05-06T00:00:00Z",
    )

    assert event.runtime is RuntimeKind.OPENHANDS
    assert event.payload["content"] == "hello"


def test_utc_now_returns_zulu_timestamp() -> None:
    timestamp = utc_now()

    assert timestamp.endswith("Z")
    assert timestamp != "1970-01-01T00:00:00Z"


def test_runtime_adapter_protocol_importable() -> None:
    assert RuntimeAdapter.__name__ == "RuntimeAdapter"
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest packages/contracts/tests/test_runtime_contracts.py -q
```

Expected: FAIL with missing imports such as `PromptBundle`.

- [ ] **Step 3: Implement shared time helper**

Create `packages/contracts/docagent_contracts/time.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
```

- [ ] **Step 4: Implement runtime contracts**

Create `packages/contracts/docagent_contracts/runtime.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from .models import SemanticTimelineEvent


class RuntimeKind(str, Enum):
    MOCK = "mock"
    OPENHANDS = "openhands"


class RuntimeSessionState(str, Enum):
    IDLE = "idle"
    RUNNING_CONTEXT = "running_context"
    AWAIT_OUTLINE_APPROVAL = "await_outline_approval"
    RUNNING_DRAFT = "running_draft"
    DRAFT_READY = "draft_ready"
    RUNNING_REVISION = "running_revision"
    RUNNING_CHECKLIST = "running_checklist"
    RUNNING_EXPORT = "running_export"
    PAUSED = "paused"
    FAILED = "failed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


@dataclass(frozen=True)
class PromptBundle:
    system_prompt: str
    task_instruction: str
    workspace_root: str
    doc_type_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RawRuntimeEvent:
    id: str
    session_id: str
    runtime: RuntimeKind
    runtime_session_id: str | None
    kind: str
    payload: dict[str, Any]
    created_at: str


@dataclass(frozen=True)
class RuntimeOperationResult:
    session_id: str
    next_state: RuntimeSessionState | None
    events: list[SemanticTimelineEvent]
    changed_paths: list[str]
    raw_events: list[RawRuntimeEvent]


class RuntimeAdapter(Protocol):
    def create_session(
        self,
        task_id: str,
        session_id: str,
        workspace_root: Path,
        doc_type_id: str,
        prompt_bundle: PromptBundle,
    ) -> RuntimeOperationResult:
        ...

    def send_message(self, task_id: str, session_id: str, workspace_root: Path, message: str) -> RuntimeOperationResult:
        ...

    def start_loop(self, task_id: str, session_id: str, workspace_root: Path) -> RuntimeOperationResult:
        ...

    def approve_outline(
        self,
        task_id: str,
        session_id: str,
        workspace_root: Path,
        outline_markdown: str,
    ) -> RuntimeOperationResult:
        ...

    def revise_selection(
        self,
        task_id: str,
        session_id: str,
        workspace_root: Path,
        selected_text: str,
        instruction: str,
    ) -> RuntimeOperationResult:
        ...

    def run_checklist(self, task_id: str, session_id: str, workspace_root: Path) -> RuntimeOperationResult:
        ...

    def export_markdown(self, task_id: str, session_id: str, workspace_root: Path) -> RuntimeOperationResult:
        ...

    def cancel(self, task_id: str, session_id: str, workspace_root: Path) -> RuntimeOperationResult:
        ...

    def get_state(self, session_id: str) -> RuntimeSessionState:
        ...
```

- [ ] **Step 5: Export runtime contracts and shared time**

Modify `packages/contracts/docagent_contracts/__init__.py` to import and export:

```python
from .runtime import (
    PromptBundle,
    RawRuntimeEvent,
    RuntimeAdapter,
    RuntimeKind,
    RuntimeOperationResult,
    RuntimeSessionState,
)
from .time import utc_now
```

Add these names to `__all__`:

```python
    "PromptBundle",
    "RawRuntimeEvent",
    "RuntimeAdapter",
    "RuntimeKind",
    "RuntimeOperationResult",
    "RuntimeSessionState",
    "utc_now",
```

- [ ] **Step 6: Add OpenHands adapter path to pytest config**

Modify `pyproject.toml` so `pythonpath` includes:

```toml
  "agent/runtime-adapters/openhands",
```

and `testpaths` includes:

```toml
  "agent/runtime-adapters/openhands/tests",
```

- [ ] **Step 7: Run contract tests**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest packages/contracts/tests/test_runtime_contracts.py packages/contracts/tests/test_models.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit Task 1**

Run:

```powershell
git add pyproject.toml packages/contracts
git commit -m "Add runtime adapter contracts"
```

## Task 2: Session State Machine And Raw Event Storage

**Files:**
- Create: `services/api/docagent_api/session_state.py`
- Modify: `services/api/docagent_api/state.py`
- Test: `services/api/tests/test_session_state.py`
- Test: `services/api/tests/test_state.py`

- [ ] **Step 1: Write failing session state tests**

Create `services/api/tests/test_session_state.py`:

```python
import pytest

from docagent_api.session_state import InvalidSessionTransition, require_transition
from docagent_contracts import RuntimeSessionState


def test_allows_start_loop_from_idle() -> None:
    assert require_transition("start_loop", RuntimeSessionState.IDLE) is RuntimeSessionState.RUNNING_CONTEXT


def test_rejects_outline_approval_before_start() -> None:
    with pytest.raises(InvalidSessionTransition, match="approve_outline requires await_outline_approval"):
        require_transition("approve_outline", RuntimeSessionState.IDLE)


def test_rejects_checklist_before_draft_ready() -> None:
    with pytest.raises(InvalidSessionTransition, match="run_checklist requires draft_ready"):
        require_transition("run_checklist", RuntimeSessionState.AWAIT_OUTLINE_APPROVAL)


def test_cancel_is_idempotent_after_cancelled() -> None:
    assert require_transition("cancel", RuntimeSessionState.CANCELLED) is RuntimeSessionState.CANCELLED
```

- [ ] **Step 2: Add failing raw event state test**

Append to `services/api/tests/test_state.py`:

```python
def test_state_persists_raw_runtime_events_as_jsonl(tmp_path: Path) -> None:
    state = DocAgentState(tmp_path)
    event = {
        "id": "raw-001",
        "session_id": "session-001",
        "runtime": "openhands",
        "runtime_session_id": "oh-001",
        "kind": "message",
        "payload": {"content": "hello"},
        "created_at": "2026-05-06T00:00:00Z",
    }

    state.append_raw_runtime_event("session-001", event)
    state.append_raw_runtime_event("session-001", {**event, "id": "raw-002"})

    assert [item["id"] for item in state.list_raw_runtime_events("session-001")] == ["raw-001", "raw-002"]
    assert (tmp_path / "raw-events" / "session-001.jsonl").exists()
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest services/api/tests/test_session_state.py services/api/tests/test_state.py::test_state_persists_raw_runtime_events_as_jsonl -q
```

Expected: FAIL because `docagent_api.session_state` and raw event methods do not exist.

- [ ] **Step 4: Implement state machine helper**

Create `services/api/docagent_api/session_state.py`:

```python
from __future__ import annotations

from docagent_contracts import RuntimeSessionState


class InvalidSessionTransition(ValueError):
    def __init__(self, operation: str, required: str, current: RuntimeSessionState) -> None:
        super().__init__(f"{operation} requires {required}; current state is {current.value}")
        self.operation = operation
        self.required = required
        self.current = current


def parse_state(value: str) -> RuntimeSessionState:
    return RuntimeSessionState(value)


def require_transition(operation: str, current: RuntimeSessionState) -> RuntimeSessionState:
    if operation == "start_loop" and current in {RuntimeSessionState.IDLE, RuntimeSessionState.FAILED}:
        return RuntimeSessionState.RUNNING_CONTEXT
    if operation == "approve_outline" and current is RuntimeSessionState.AWAIT_OUTLINE_APPROVAL:
        return RuntimeSessionState.RUNNING_DRAFT
    if operation == "revise_selection" and current is RuntimeSessionState.DRAFT_READY:
        return RuntimeSessionState.RUNNING_REVISION
    if operation == "run_checklist" and current is RuntimeSessionState.DRAFT_READY:
        return RuntimeSessionState.RUNNING_CHECKLIST
    if operation == "export_markdown" and current is RuntimeSessionState.DRAFT_READY:
        return RuntimeSessionState.RUNNING_EXPORT
    if operation == "cancel":
        if current in {RuntimeSessionState.CANCELLED, RuntimeSessionState.COMPLETED}:
            return current
        if current.value.startswith("running_"):
            return RuntimeSessionState.CANCELLED
        raise InvalidSessionTransition(operation, "a running state", current)

    requirements = {
        "start_loop": "idle or failed",
        "approve_outline": "await_outline_approval",
        "revise_selection": "draft_ready",
        "run_checklist": "draft_ready",
        "export_markdown": "draft_ready",
    }
    raise InvalidSessionTransition(operation, requirements.get(operation, "a valid state"), current)
```

- [ ] **Step 5: Add raw event JSONL methods**

Modify `services/api/docagent_api/state.py`:

```python
        (self.root / "raw-events").mkdir(parents=True, exist_ok=True)
```

Add methods:

```python
    def append_raw_runtime_event(self, session_id: str, event: dict[str, Any]) -> None:
        path = self._raw_events_path(session_id)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def list_raw_runtime_events(self, session_id: str) -> list[dict[str, Any]]:
        path = self._raw_events_path(session_id)
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _raw_events_path(self, session_id: str) -> Path:
        return self.root / "raw-events" / f"{session_id}.jsonl"
```

- [ ] **Step 6: Run state tests**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest services/api/tests/test_session_state.py services/api/tests/test_state.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 2**

Run:

```powershell
git add services/api/docagent_api/session_state.py services/api/docagent_api/state.py services/api/tests/test_session_state.py services/api/tests/test_state.py
git commit -m "Add runtime session state and raw event storage"
```

## Task 3: Prompt Assembly Helper

**Files:**
- Create: `services/api/docagent_api/prompts.py`
- Test: `services/api/tests/test_prompts.py`

- [ ] **Step 1: Write failing prompt tests**

Create `services/api/tests/test_prompts.py`:

```python
from pathlib import Path

from docagent_api.prompts import build_prompt_bundle


def test_build_prompt_bundle_reads_core_prompt_and_skill(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    workspace = tmp_path / "workspace"
    (repo / "agent" / "system-prompts").mkdir(parents=True)
    (repo / "doc-types" / "prd").mkdir(parents=True)
    (repo / "agent" / "system-prompts" / "docagent-core.md").write_text("Core prompt\n", encoding="utf-8")
    (repo / "doc-types" / "prd" / "SKILL.md").write_text("PRD skill\n", encoding="utf-8")
    workspace.mkdir()

    bundle = build_prompt_bundle(
        repo_root=repo,
        workspace_root=workspace,
        task_id="task-001",
        session_id="session-001",
        doc_type_id="prd",
    )

    assert "Core prompt" in bundle.system_prompt
    assert "PRD skill" in bundle.system_prompt
    assert "task-001" in bundle.task_instruction
    assert bundle.metadata["session_id"] == "session-001"
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest services/api/tests/test_prompts.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'docagent_api.prompts'`.

- [ ] **Step 3: Implement prompt helper**

Create `services/api/docagent_api/prompts.py`:

```python
from __future__ import annotations

from pathlib import Path

from docagent_contracts import PromptBundle


def build_prompt_bundle(
    repo_root: Path,
    workspace_root: Path,
    task_id: str,
    session_id: str,
    doc_type_id: str,
) -> PromptBundle:
    core_prompt = _read_required(repo_root / "agent" / "system-prompts" / "docagent-core.md")
    skill = _read_required(repo_root / "doc-types" / doc_type_id / "SKILL.md")
    system_prompt = f"{core_prompt.rstrip()}\n\n---\n\n{skill.rstrip()}\n"
    task_instruction = (
        f"Task id: {task_id}\n"
        f"Session id: {session_id}\n"
        f"Document type: {doc_type_id}\n"
        f"Workspace root: {workspace_root}\n"
        "Use Markdown-facing resources only. Write outputs to the workspace contract paths.\n"
    )
    return PromptBundle(
        system_prompt=system_prompt,
        task_instruction=task_instruction,
        workspace_root=str(workspace_root),
        doc_type_id=doc_type_id,
        metadata={"task_id": task_id, "session_id": session_id},
    )


def _read_required(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)
    return path.read_text(encoding="utf-8")
```

- [ ] **Step 4: Run prompt tests**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest services/api/tests/test_prompts.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

Run:

```powershell
git add services/api/docagent_api/prompts.py services/api/tests/test_prompts.py
git commit -m "Add runtime prompt assembly"
```

## Task 4: Move Mock Adapter Behind Formal Contract

**Files:**
- Modify: `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py`
- Test: `agent/runtime-adapters/mock/tests/test_adapter.py`
- Test: `agent/runtime-adapters/mock/tests/test_authoring_loop.py`

- [ ] **Step 1: Add failing formal result test**

Append to `agent/runtime-adapters/mock/tests/test_authoring_loop.py`:

```python
from docagent_contracts import PromptBundle, RuntimeOperationResult, RuntimeSessionState


def test_mock_start_loop_returns_runtime_operation_result(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "brief.md").write_text("Build a PRD for onboarding analytics\n", encoding="utf-8")
    adapter = MockRuntimeAdapter()

    result = adapter.start_loop("task-001", "session-001", workspace)

    assert isinstance(result, RuntimeOperationResult)
    assert result.next_state is RuntimeSessionState.AWAIT_OUTLINE_APPROVAL
    assert "draft/outline.md" in result.changed_paths


def test_mock_send_message_returns_runtime_operation_result(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "brief.md").write_text("Build a PRD for onboarding analytics\n", encoding="utf-8")
    adapter = MockRuntimeAdapter()

    result = adapter.send_message("task-001", "session-001", workspace, "Start the PRD")

    assert isinstance(result, RuntimeOperationResult)
    assert len(result.events) == 6
    assert "draft/draft.md" in result.changed_paths


def test_mock_create_session_is_noop_result(tmp_path: Path) -> None:
    adapter = MockRuntimeAdapter()
    bundle = PromptBundle(
        system_prompt="core",
        task_instruction="task",
        workspace_root=str(tmp_path),
        doc_type_id="prd",
        metadata={},
    )

    result = adapter.create_session("task-001", "session-001", tmp_path, "prd", bundle)

    assert result.session_id == "session-001"
    assert result.events == []
```

- [ ] **Step 2: Run mock tests and verify failure**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest agent/runtime-adapters/mock/tests/test_authoring_loop.py::test_mock_start_loop_returns_runtime_operation_result agent/runtime-adapters/mock/tests/test_authoring_loop.py::test_mock_create_session_is_noop_result -q
```

Expected: FAIL because mock methods do not return `RuntimeOperationResult`.

- [ ] **Step 3: Rename event-producing methods to private helpers**

Modify `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py` so public adapter methods can use the formal result type. Rename the current event-list methods:

```python
send_message -> _send_message_events
build_context_and_outline -> _build_context_and_outline_events
approve_outline_and_draft -> _approve_outline_and_draft_events
revise_selection -> _revise_selection_events
run_checklist -> _run_checklist_events
export_markdown -> _export_markdown_events
```

For example, the first method becomes:

```python
    def _send_message_events(
        self,
        task_id: str,
        session_id: str,
        workspace_root: Path,
        message: str,
    ) -> list[SemanticTimelineEvent]:
        if (workspace_root / "draft" / "draft.md").exists():
            return self._revise(task_id, session_id, workspace_root, message)
        return self._first_draft(task_id, session_id, workspace_root, message)
```

The authoring-loop helpers keep their existing bodies and return `list[SemanticTimelineEvent]`; only their names change.

- [ ] **Step 4: Add result helper and formal public methods**

Modify `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py` imports:

```python
from docagent_contracts import (
    PromptBundle,
    RawRuntimeEvent,
    RuntimeKind,
    RuntimeOperationResult,
    RuntimeSessionState,
    SemanticEventKind,
    SemanticTimelineEvent,
    TimelineActor,
    TimelineStatus,
)
```

Add methods inside `MockRuntimeAdapter`:

```python
    def create_session(
        self,
        task_id: str,
        session_id: str,
        workspace_root: Path,
        doc_type_id: str,
        prompt_bundle: PromptBundle,
    ) -> RuntimeOperationResult:
        return _result(session_id, None, [], [], [])

    def send_message(
        self,
        task_id: str,
        session_id: str,
        workspace_root: Path,
        message: str,
    ) -> RuntimeOperationResult:
        events = self._send_message_events(task_id, session_id, workspace_root, message)
        return _result(session_id, RuntimeSessionState.DRAFT_READY, events, _event_paths(events), [])

    def start_loop(self, task_id: str, session_id: str, workspace_root: Path) -> RuntimeOperationResult:
        events = self._build_context_and_outline_events(task_id, session_id, workspace_root)
        return _result(session_id, RuntimeSessionState.AWAIT_OUTLINE_APPROVAL, events, _event_paths(events), [])

    def approve_outline(
        self,
        task_id: str,
        session_id: str,
        workspace_root: Path,
        outline_markdown: str,
    ) -> RuntimeOperationResult:
        events = self._approve_outline_and_draft_events(task_id, session_id, workspace_root, outline_markdown)
        return _result(session_id, RuntimeSessionState.DRAFT_READY, events, _event_paths(events), [])

    def revise_selection(
        self,
        task_id: str,
        session_id: str,
        workspace_root: Path,
        selected_text: str,
        instruction: str,
    ) -> RuntimeOperationResult:
        events = self._revise_selection_events(task_id, session_id, workspace_root, selected_text, instruction)
        return _result(session_id, RuntimeSessionState.DRAFT_READY, events, _event_paths(events), [])

    def run_checklist(self, task_id: str, session_id: str, workspace_root: Path) -> RuntimeOperationResult:
        events = self._run_checklist_events(task_id, session_id, workspace_root)
        return _result(session_id, RuntimeSessionState.DRAFT_READY, events, _event_paths(events), [])

    def export_markdown(self, task_id: str, session_id: str, workspace_root: Path) -> RuntimeOperationResult:
        events = self._export_markdown_events(task_id, session_id, workspace_root)
        return _result(session_id, RuntimeSessionState.DRAFT_READY, events, _event_paths(events), [])

    def cancel(self, task_id: str, session_id: str, workspace_root: Path) -> RuntimeOperationResult:
        return _result(session_id, RuntimeSessionState.CANCELLED, [], [], [])

    def get_state(self, session_id: str) -> RuntimeSessionState:
        return RuntimeSessionState.IDLE
```

Add module helpers:

```python
def _result(
    session_id: str,
    next_state: RuntimeSessionState | None,
    events: list[SemanticTimelineEvent],
    changed_paths: list[str],
    raw_events: list[RawRuntimeEvent],
) -> RuntimeOperationResult:
    return RuntimeOperationResult(
        session_id=session_id,
        next_state=next_state,
        events=events,
        changed_paths=changed_paths,
        raw_events=raw_events,
    )


def _event_paths(events: list[SemanticTimelineEvent]) -> list[str]:
    return [path for event in events for path in event.paths]
```

- [ ] **Step 5: Update mock tests to assert result events**

Update existing mock adapter tests that currently expect a raw event list:

```python
result = adapter.revise_selection(...)
events = result.events
```

```python
checklist_result = adapter.run_checklist(...)
export_result = adapter.export_markdown(...)
checklist_events = checklist_result.events
export_events = export_result.events
```

For tests that call `send_message`, use:

```python
result = adapter.send_message(...)
events = result.events
```

- [ ] **Step 6: Run mock tests**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest agent/runtime-adapters/mock/tests -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 4**

Run:

```powershell
git add agent/runtime-adapters/mock
git commit -m "Move mock runtime behind adapter contract"
```

## Task 5: Runtime Factory

**Files:**
- Create: `services/api/docagent_api/runtime_factory.py`
- Test: `services/api/tests/test_runtime_factory.py`

- [ ] **Step 1: Write failing factory tests**

Create `services/api/tests/test_runtime_factory.py`:

```python
import pytest

from docagent_api.runtime_factory import RuntimeConfigurationError, create_runtime_adapter
from docagent_mock_runtime.adapter import MockRuntimeAdapter


def test_factory_defaults_to_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DOCAGENT_RUNTIME", raising=False)

    adapter = create_runtime_adapter()

    assert isinstance(adapter, MockRuntimeAdapter)


def test_factory_rejects_unknown_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCAGENT_RUNTIME", "unknown")

    with pytest.raises(RuntimeConfigurationError, match="Unsupported DOCAGENT_RUNTIME"):
        create_runtime_adapter()
```

- [ ] **Step 2: Run factory tests and verify failure**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest services/api/tests/test_runtime_factory.py -q
```

Expected: FAIL because `docagent_api.runtime_factory` does not exist.

- [ ] **Step 3: Implement factory**

Create `services/api/docagent_api/runtime_factory.py`:

```python
from __future__ import annotations

import os

from docagent_contracts import RuntimeAdapter, RuntimeKind
from docagent_mock_runtime.adapter import MockRuntimeAdapter


class RuntimeConfigurationError(ValueError):
    pass


def create_runtime_adapter(runtime_name: str | None = None) -> RuntimeAdapter:
    selected = (runtime_name or os.getenv("DOCAGENT_RUNTIME") or RuntimeKind.MOCK.value).lower()
    if selected == RuntimeKind.MOCK.value:
        return MockRuntimeAdapter()
    if selected == RuntimeKind.OPENHANDS.value:
        from docagent_openhands_runtime.adapter import OpenHandsRuntimeAdapter
        from docagent_openhands_runtime.client import OpenHandsAgentServerClient

        return OpenHandsRuntimeAdapter(client=OpenHandsAgentServerClient.from_env())
    raise RuntimeConfigurationError(f"Unsupported DOCAGENT_RUNTIME: {selected}")
```

- [ ] **Step 4: Run factory tests**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest services/api/tests/test_runtime_factory.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 5**

Run:

```powershell
git add services/api/docagent_api/runtime_factory.py services/api/tests/test_runtime_factory.py
git commit -m "Add runtime adapter factory"
```

## Task 6: OpenHands Adapter With Fake Client

**Files:**
- Create: `agent/runtime-adapters/openhands/docagent_openhands_runtime/__init__.py`
- Create: `agent/runtime-adapters/openhands/docagent_openhands_runtime/client.py`
- Create: `agent/runtime-adapters/openhands/docagent_openhands_runtime/adapter.py`
- Test: `agent/runtime-adapters/openhands/tests/test_adapter.py`

- [ ] **Step 1: Write failing OpenHands fake-client tests**

Create `agent/runtime-adapters/openhands/tests/test_adapter.py`:

```python
from pathlib import Path

import pytest

from docagent_contracts import PromptBundle, RuntimeSessionState
from docagent_openhands_runtime.adapter import OpenHandsRuntimeAdapter


class FakeOpenHandsClient:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []
        self.cancelled: list[str] = []

    def create_conversation(self, workspace_root: Path, prompt_bundle: PromptBundle) -> str:
        return "oh-session-001"

    def send_message(self, runtime_session_id: str, message: str) -> None:
        self.messages.append((runtime_session_id, message))

    def stream_events(self, runtime_session_id: str) -> list[dict[str, object]]:
        return [
            {"id": "raw-001", "type": "message", "content": "working"},
            {"id": "raw-002", "type": "file_write", "path": "draft/outline.md"},
        ]

    def cancel(self, runtime_session_id: str) -> None:
        self.cancelled.append(runtime_session_id)


def test_openhands_create_session_tracks_runtime_session(tmp_path: Path) -> None:
    adapter = OpenHandsRuntimeAdapter(client=FakeOpenHandsClient())
    bundle = PromptBundle("core", "task", str(tmp_path), "prd", {})

    result = adapter.create_session("task-001", "session-001", tmp_path, "prd", bundle)

    assert result.session_id == "session-001"
    assert result.raw_events[0].runtime_session_id == "oh-session-001"


def test_openhands_start_loop_collects_raw_events(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    adapter = OpenHandsRuntimeAdapter(client=FakeOpenHandsClient())
    bundle = PromptBundle("core", "task", str(workspace), "prd", {})
    adapter.create_session("task-001", "session-001", workspace, "prd", bundle)

    result = adapter.start_loop("task-001", "session-001", workspace)

    assert result.next_state is RuntimeSessionState.AWAIT_OUTLINE_APPROVAL
    assert [event.kind for event in result.raw_events] == ["message", "file_write"]


def test_openhands_cancel_requires_known_session(tmp_path: Path) -> None:
    adapter = OpenHandsRuntimeAdapter(client=FakeOpenHandsClient())

    with pytest.raises(KeyError, match="session-404"):
        adapter.cancel("task-001", "session-404", tmp_path)
```

- [ ] **Step 2: Run OpenHands tests and verify failure**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest agent/runtime-adapters/openhands/tests/test_adapter.py -q
```

Expected: FAIL because `docagent_openhands_runtime` does not exist.

- [ ] **Step 3: Implement OpenHands client wrapper**

Create `agent/runtime-adapters/openhands/docagent_openhands_runtime/client.py`:

```python
from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from docagent_contracts import PromptBundle


class OpenHandsClient(Protocol):
    def create_conversation(self, workspace_root: Path, prompt_bundle: PromptBundle) -> str:
        ...

    def send_message(self, runtime_session_id: str, message: str) -> None:
        ...

    def stream_events(self, runtime_session_id: str) -> list[dict[str, object]]:
        ...

    def cancel(self, runtime_session_id: str) -> None:
        ...


class OpenHandsAgentServerClient:
    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        self.base_url = base_url
        self.api_key = api_key

    @classmethod
    def from_env(cls) -> "OpenHandsAgentServerClient":
        base_url = os.getenv("OPENHANDS_BASE_URL")
        if not base_url:
            raise RuntimeError("OPENHANDS_BASE_URL is required when DOCAGENT_RUNTIME=openhands")
        return cls(base_url=base_url, api_key=os.getenv("OPENHANDS_API_KEY"))

    def create_conversation(self, workspace_root: Path, prompt_bundle: PromptBundle) -> str:
        try:
            from openhands.client import AgentServerClient
        except ModuleNotFoundError as exc:
            raise RuntimeError("OpenHands SDK is not installed. Install the OpenHands client package first.") from exc

        client = AgentServerClient(url=self.base_url, api_key=self.api_key)
        conversation = client.create_conversation()
        client.send_message(conversation_id=conversation.id, message=prompt_bundle.system_prompt + "\n\n" + prompt_bundle.task_instruction)
        return str(conversation.id)

    def send_message(self, runtime_session_id: str, message: str) -> None:
        from openhands.client import AgentServerClient

        client = AgentServerClient(url=self.base_url, api_key=self.api_key)
        client.send_message(conversation_id=runtime_session_id, message=message)

    def stream_events(self, runtime_session_id: str) -> list[dict[str, object]]:
        from openhands.client import AgentServerClient

        client = AgentServerClient(url=self.base_url, api_key=self.api_key)
        return [getattr(event, "model_dump", lambda: event)() for event in client.stream_conversation(runtime_session_id)]

    def cancel(self, runtime_session_id: str) -> None:
        self.send_message(runtime_session_id, "Cancel the current operation and stop.")
```

Keep normal tests fake-client based. The real SDK import and method names are isolated in this file so any later OpenHands SDK adjustment is limited to `client.py`.

- [ ] **Step 4: Implement OpenHands adapter**

Create `agent/runtime-adapters/openhands/docagent_openhands_runtime/adapter.py`:

```python
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from docagent_contracts import (
    PromptBundle,
    RawRuntimeEvent,
    RuntimeKind,
    RuntimeOperationResult,
    RuntimeSessionState,
    SemanticTimelineEvent,
)
from docagent_contracts import utc_now

from .client import OpenHandsClient


class OpenHandsRuntimeAdapter:
    def __init__(self, client: OpenHandsClient) -> None:
        self.client = client
        self._runtime_sessions: dict[str, str] = {}

    def create_session(
        self,
        task_id: str,
        session_id: str,
        workspace_root: Path,
        doc_type_id: str,
        prompt_bundle: PromptBundle,
    ) -> RuntimeOperationResult:
        runtime_session_id = self.client.create_conversation(workspace_root, prompt_bundle)
        self._runtime_sessions[session_id] = runtime_session_id
        raw = RawRuntimeEvent(
            id=f"raw-{uuid4().hex[:8]}",
            session_id=session_id,
            runtime=RuntimeKind.OPENHANDS,
            runtime_session_id=runtime_session_id,
            kind="session_created",
            payload={"doc_type_id": doc_type_id},
            created_at=utc_now(),
        )
        return _result(session_id, None, [], [], [raw])

    def send_message(self, task_id: str, session_id: str, workspace_root: Path, message: str) -> RuntimeOperationResult:
        runtime_session_id = self._require_runtime_session(session_id)
        self.client.send_message(runtime_session_id, message)
        return self._collect(session_id, RuntimeSessionState.DRAFT_READY)

    def start_loop(self, task_id: str, session_id: str, workspace_root: Path) -> RuntimeOperationResult:
        runtime_session_id = self._require_runtime_session(session_id)
        self.client.send_message(runtime_session_id, "Build context files and propose an outline. Stop after writing draft/outline.md.")
        return self._collect(session_id, RuntimeSessionState.AWAIT_OUTLINE_APPROVAL)

    def approve_outline(
        self,
        task_id: str,
        session_id: str,
        workspace_root: Path,
        outline_markdown: str,
    ) -> RuntimeOperationResult:
        runtime_session_id = self._require_runtime_session(session_id)
        self.client.send_message(runtime_session_id, f"Use this approved outline and generate draft/draft.md:\n\n{outline_markdown}")
        return self._collect(session_id, RuntimeSessionState.DRAFT_READY)

    def revise_selection(
        self,
        task_id: str,
        session_id: str,
        workspace_root: Path,
        selected_text: str,
        instruction: str,
    ) -> RuntimeOperationResult:
        runtime_session_id = self._require_runtime_session(session_id)
        message = (
            "Before revising, create a checkpoint. Then revise only this selected text in draft/draft.md.\n"
            f"Selected text:\n{selected_text}\n\nInstruction:\n{instruction}"
        )
        self.client.send_message(runtime_session_id, message)
        return self._collect(session_id, RuntimeSessionState.DRAFT_READY)

    def run_checklist(self, task_id: str, session_id: str, workspace_root: Path) -> RuntimeOperationResult:
        runtime_session_id = self._require_runtime_session(session_id)
        self.client.send_message(runtime_session_id, "Run the document checklist and write reviews/checklist_result.md.")
        return self._collect(session_id, RuntimeSessionState.DRAFT_READY)

    def export_markdown(self, task_id: str, session_id: str, workspace_root: Path) -> RuntimeOperationResult:
        runtime_session_id = self._require_runtime_session(session_id)
        self.client.send_message(runtime_session_id, "Copy the current draft to artifacts/prd-draft.md.")
        return self._collect(session_id, RuntimeSessionState.DRAFT_READY)

    def cancel(self, task_id: str, session_id: str, workspace_root: Path) -> RuntimeOperationResult:
        runtime_session_id = self._require_runtime_session(session_id)
        self.client.cancel(runtime_session_id)
        return _result(session_id, RuntimeSessionState.CANCELLED, [], [], [])

    def get_state(self, session_id: str) -> RuntimeSessionState:
        self._require_runtime_session(session_id)
        return RuntimeSessionState.IDLE

    def _collect(self, session_id: str, next_state: RuntimeSessionState) -> RuntimeOperationResult:
        runtime_session_id = self._require_runtime_session(session_id)
        raw_events = [
            _raw_event(session_id, runtime_session_id, event)
            for event in self.client.stream_events(runtime_session_id)
        ]
        return _result(session_id, next_state, [], _changed_paths(raw_events), raw_events)

    def _require_runtime_session(self, session_id: str) -> str:
        if session_id not in self._runtime_sessions:
            raise KeyError(session_id)
        return self._runtime_sessions[session_id]


def _raw_event(session_id: str, runtime_session_id: str, payload: dict[str, object]) -> RawRuntimeEvent:
    kind = str(payload.get("type", payload.get("kind", "unknown")))
    return RawRuntimeEvent(
        id=str(payload.get("id", f"raw-{uuid4().hex[:8]}")),
        session_id=session_id,
        runtime=RuntimeKind.OPENHANDS,
        runtime_session_id=runtime_session_id,
        kind=kind,
        payload=dict(payload),
        created_at=utc_now(),
    )


def _changed_paths(raw_events: list[RawRuntimeEvent]) -> list[str]:
    paths: list[str] = []
    for event in raw_events:
        path = event.payload.get("path")
        if isinstance(path, str):
            paths.append(path)
    return paths


def _result(
    session_id: str,
    next_state: RuntimeSessionState | None,
    events: list[SemanticTimelineEvent],
    changed_paths: list[str],
    raw_events: list[RawRuntimeEvent],
) -> RuntimeOperationResult:
    return RuntimeOperationResult(
        session_id=session_id,
        next_state=next_state,
        events=events,
        changed_paths=changed_paths,
        raw_events=raw_events,
    )
```

Create `agent/runtime-adapters/openhands/docagent_openhands_runtime/__init__.py`:

```python
from .adapter import OpenHandsRuntimeAdapter

__all__ = ["OpenHandsRuntimeAdapter"]
```

- [ ] **Step 5: Run OpenHands fake-client tests**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest agent/runtime-adapters/openhands/tests/test_adapter.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 6**

Run:

```powershell
git add agent/runtime-adapters/openhands
git commit -m "Add OpenHands runtime adapter first slice"
```

## Task 7: OpenHands Raw Event Mapper

**Files:**
- Create: `packages/timeline/docagent_timeline/openhands_mapper.py`
- Modify: `packages/timeline/docagent_timeline/__init__.py`
- Test: `packages/timeline/tests/test_openhands_mapper.py`

- [ ] **Step 1: Write failing mapper tests**

Create `packages/timeline/tests/test_openhands_mapper.py`:

```python
from docagent_contracts import RawRuntimeEvent, RuntimeKind, SemanticEventKind
from docagent_timeline import map_openhands_raw_event


def _raw(kind: str, payload: dict[str, object]) -> RawRuntimeEvent:
    return RawRuntimeEvent(
        id="raw-001",
        session_id="session-001",
        runtime=RuntimeKind.OPENHANDS,
        runtime_session_id="oh-001",
        kind=kind,
        payload=payload,
        created_at="2026-05-06T00:00:00Z",
    )


def test_maps_outline_write_to_propose_outline() -> None:
    event = map_openhands_raw_event("task-001", _raw("file_write", {"path": "draft/outline.md"}))

    assert event.kind is SemanticEventKind.PROPOSE_OUTLINE


def test_maps_draft_write_to_update_draft() -> None:
    event = map_openhands_raw_event("task-001", _raw("file_write", {"path": "draft/draft.md"}))

    assert event.kind is SemanticEventKind.UPDATE_DRAFT


def test_maps_runtime_error() -> None:
    event = map_openhands_raw_event("task-001", _raw("error", {"message": "boom"}))

    assert event.kind is SemanticEventKind.ERROR
    assert event.status.value == "failed"
```

- [ ] **Step 2: Run mapper tests and verify failure**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest packages/timeline/tests/test_openhands_mapper.py -q
```

Expected: FAIL because `map_openhands_raw_event` does not exist.

- [ ] **Step 3: Implement mapper**

Create `packages/timeline/docagent_timeline/openhands_mapper.py`:

```python
from __future__ import annotations

from docagent_contracts import (
    RawRuntimeEvent,
    SemanticEventKind,
    SemanticTimelineEvent,
    TimelineActor,
    TimelineStatus,
)


def map_openhands_raw_event(task_id: str, raw_event: RawRuntimeEvent) -> SemanticTimelineEvent:
    path = raw_event.payload.get("path")
    normalized_path = path.replace("\\", "/") if isinstance(path, str) else ""
    kind = _kind_for(raw_event.kind, normalized_path)
    status = TimelineStatus.FAILED if kind is SemanticEventKind.ERROR else TimelineStatus.SUCCEEDED
    return SemanticTimelineEvent(
        id=f"sem-{raw_event.id}",
        session_id=raw_event.session_id,
        task_id=task_id,
        actor=TimelineActor.AGENT,
        kind=kind,
        raw_event_id=raw_event.id,
        summary=_summary_for(kind),
        paths=[normalized_path] if normalized_path else [],
        status=status,
        created_at=raw_event.created_at,
    )


def _kind_for(raw_kind: str, path: str) -> SemanticEventKind:
    if raw_kind == "error":
        return SemanticEventKind.ERROR
    if path.endswith("context/user_intent.md") or path.endswith("context/doc_map.md"):
        return SemanticEventKind.BUILD_CONTEXT
    if path.endswith("context/style_notes.md"):
        return SemanticEventKind.EXTRACT_STYLE
    if path.endswith("context/structure_notes.md"):
        return SemanticEventKind.EXTRACT_STRUCTURE
    if path.endswith("draft/outline.md"):
        return SemanticEventKind.PROPOSE_OUTLINE
    if path.endswith("draft/draft.md"):
        return SemanticEventKind.UPDATE_DRAFT
    if path.startswith("versions/"):
        return SemanticEventKind.CREATE_CHECKPOINT
    if path.endswith("reviews/checklist_result.md"):
        return SemanticEventKind.RUN_CHECKLIST
    if path.startswith("artifacts/"):
        return SemanticEventKind.EXPORT_MARKDOWN
    return SemanticEventKind.AGENT_MESSAGE


def _summary_for(kind: SemanticEventKind) -> str:
    return {
        SemanticEventKind.BUILD_CONTEXT: "Build context files",
        SemanticEventKind.EXTRACT_STYLE: "Extract style notes",
        SemanticEventKind.EXTRACT_STRUCTURE: "Extract structure notes",
        SemanticEventKind.PROPOSE_OUTLINE: "Propose outline",
        SemanticEventKind.UPDATE_DRAFT: "Update draft",
        SemanticEventKind.CREATE_CHECKPOINT: "Create checkpoint",
        SemanticEventKind.RUN_CHECKLIST: "Run checklist",
        SemanticEventKind.EXPORT_MARKDOWN: "Export Markdown artifact",
        SemanticEventKind.ERROR: "Runtime error",
    }.get(kind, "Agent event")
```

Modify `packages/timeline/docagent_timeline/__init__.py`:

```python
from .openhands_mapper import map_openhands_raw_event
```

Add `"map_openhands_raw_event"` to `__all__`.

- [ ] **Step 4: Run timeline tests**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest packages/timeline/tests -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 7**

Run:

```powershell
git add packages/timeline
git commit -m "Map OpenHands raw events to semantic timeline"
```

## Task 8: Rewire API To Runtime Factory And State Machine

**Files:**
- Modify: `services/api/docagent_api/app.py`
- Test: `services/api/tests/test_phase3_api.py`
- Test: `services/api/tests/test_phase2_api.py`
- Test: `services/api/tests/test_api.py`

- [ ] **Step 1: Write failing Phase 3 API tests**

Create `services/api/tests/test_phase3_api.py`:

```python
from pathlib import Path

from fastapi.testclient import TestClient

from docagent_api.app import create_app


def test_invalid_outline_approval_returns_409(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build onboarding analytics"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    response = client.post(
        f"/sessions/{session['id']}/outline/approve",
        json={"outline_markdown": "# Outline\n"},
    )

    assert response.status_code == 409
    assert "approve_outline requires await_outline_approval" in response.json()["detail"]


def test_cancel_running_session_returns_cancelled(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build onboarding analytics"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    client.post(f"/sessions/{session['id']}/loop/start")
    # Force a running state to exercise the endpoint without a slow runtime.
    state_file = tmp_path / "state" / "sessions.json"
    data = state_file.read_text(encoding="utf-8")
    state_file.write_text(data.replace("await_outline_approval", "running_context"), encoding="utf-8")

    response = client.post(f"/sessions/{session['id']}/cancel")

    assert response.status_code == 200
    assert response.json()["next_state"] == "cancelled"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest services/api/tests/test_phase3_api.py -q
```

Expected: FAIL because `create_app` does not accept `runtime_name` and cancel endpoint does not exist.

- [ ] **Step 3: Modify app imports and adapter creation**

In `services/api/docagent_api/app.py`, remove:

```python
from docagent_mock_runtime.adapter import MockRuntimeAdapter
```

Add:

```python
from docagent_api.prompts import build_prompt_bundle
from docagent_api.runtime_factory import create_runtime_adapter
from docagent_api.session_state import InvalidSessionTransition, parse_state, require_transition
from docagent_timeline import map_openhands_raw_event
from docagent_contracts import RuntimeKind, RuntimeOperationResult, RuntimeSessionState
```

Change the function signature:

```python
def create_app(
    state_root: Path | None = None,
    repo_root: Path | None = None,
    runtime_name: str | None = None,
) -> FastAPI:
```

Replace adapter construction:

```python
    adapter = create_runtime_adapter(runtime_name)
```

- [ ] **Step 4: Add append result and transition helpers**

Add helpers in `app.py`:

```python
def _set_session_state(state: DocAgentState, session: dict[str, Any], next_state: RuntimeSessionState) -> None:
    session["status"] = next_state.value
    session["updated_at"] = utc_now()
    state.save_session(session)


def _prepare_transition(operation: str, session: dict[str, Any]) -> RuntimeSessionState:
    return require_transition(operation, parse_state(session["status"]))


def _append_runtime_result(
    state: DocAgentState,
    task_id: str,
    result: RuntimeOperationResult,
) -> None:
    for raw_event in result.raw_events:
        raw_dict = asdict(raw_event)
        state.append_raw_runtime_event(result.session_id, raw_dict)
        if raw_event.runtime is RuntimeKind.OPENHANDS:
            state.append_timeline_event(result.session_id, asdict(map_openhands_raw_event(task_id, raw_event)))
    for event in result.events:
        state.append_timeline_event(result.session_id, asdict(event))
```

Add error mapper in each stateful endpoint:

```python
        except InvalidSessionTransition as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
```

- [ ] **Step 5: Rewire create_session endpoint**

In `create_session`, replace the initial task lookup:

```python
        _require_task(state, task_id)
```

with:

```python
        task = _require_task(state, task_id)
```

After record creation and before `state.save_session(record)`, build prompt and call adapter:

```python
        prompt_bundle = build_prompt_bundle(
            repo_root=root,
            workspace_root=Path(task["workspace_root"]),
            task_id=task_id,
            session_id=session_id,
            doc_type_id=task["doc_type_id"],
        )
        result = adapter.create_session(
            task_id=task_id,
            session_id=session_id,
            workspace_root=Path(task["workspace_root"]),
            doc_type_id=task["doc_type_id"],
            prompt_bundle=prompt_bundle,
        )
```

Save the session record, then call:

```python
        _append_runtime_result(state, task_id, result)
```

- [ ] **Step 6: Rewire stateful endpoints to formal adapter methods**

For `start_loop`:

```python
        try:
            _set_session_state(state, session, _prepare_transition("start_loop", session))
            result = adapter.start_loop(task["id"], session_id, Path(task["workspace_root"]))
        except InvalidSessionTransition as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        _append_runtime_result(state, task["id"], result)
        if result.next_state:
            _set_session_state(state, session, result.next_state)
        return {"session_id": session_id, "next_state": session["status"], "event_count": len(result.events)}
```

Apply the same shape to:

- `outline/approve` with operation `approve_outline`
- `revision/selection` with operation `revise_selection`
- `checklist/run` with operation `run_checklist`
- `artifacts/export-markdown` with operation `export_markdown`

Use only the formal adapter methods introduced in Task 4:

- `adapter.start_loop(...)`
- `adapter.approve_outline(...)`
- `adapter.revise_selection(...)`
- `adapter.run_checklist(...)`
- `adapter.export_markdown(...)`

All of these methods return `RuntimeOperationResult`.

- [ ] **Step 7: Add cancel endpoint**

Add endpoint:

```python
    @app.post("/sessions/{session_id}/cancel")
    def cancel_session(session_id: str) -> dict[str, Any]:
        session = _require_session(state, session_id)
        task = _require_task(state, session["task_id"])
        try:
            _set_session_state(state, session, _prepare_transition("cancel", session))
            result = adapter.cancel(task["id"], session_id, Path(task["workspace_root"]))
        except InvalidSessionTransition as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        _append_runtime_result(state, task["id"], result)
        if result.next_state:
            _set_session_state(state, session, result.next_state)
        return {"session_id": session_id, "next_state": session["status"]}
```

- [ ] **Step 8: Run API tests**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest services/api/tests/test_phase3_api.py services/api/tests/test_phase2_api.py services/api/tests/test_api.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit Task 8**

Run:

```powershell
git add services/api/docagent_api/app.py services/api/tests/test_phase3_api.py services/api/tests/test_phase2_api.py services/api/tests/test_api.py
git commit -m "Route API through runtime adapter factory"
```

## Task 9: Documentation And Opt-In Smoke Script

**Files:**
- Create: `tools/runtime/openhands_smoke.py`
- Modify: `agent/runtime-adapters/README.md`
- Modify: `services/api/README.md`
- Modify: `docs/quality/testing.md`

- [ ] **Step 1: Create smoke script**

Create `tools/runtime/openhands_smoke.py`:

```python
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from docagent_api.app import create_app


def main() -> int:
    client = TestClient(create_app(repo_root=Path("."), runtime_name="openhands"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build onboarding analytics"}).json()
    print("created task")
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    print("created session")
    client.post(f"/tasks/{task['id']}/inputs/text", json={"name": "research.txt", "content": "Users need funnel visibility."})
    start = client.post(f"/sessions/{session['id']}/loop/start")
    start.raise_for_status()
    print("started loop")
    outline = client.get(f"/tasks/{task['id']}/workspace/files", params={"path": "draft/outline.md"}).json()
    approve = client.post(f"/sessions/{session['id']}/outline/approve", json={"outline_markdown": outline["content"]})
    approve.raise_for_status()
    print("approved outline")
    draft = client.get(f"/tasks/{task['id']}/draft").json()["markdown"]
    selected = "Build onboarding analytics" if "Build onboarding analytics" in draft else draft.splitlines()[0]
    revise = client.post(
        f"/sessions/{session['id']}/revision/selection",
        json={"selected_text": selected, "instruction": "Make this more specific."},
    )
    revise.raise_for_status()
    print("revised selection")
    client.post(f"/sessions/{session['id']}/checklist/run").raise_for_status()
    print("ran checklist")
    client.post(f"/sessions/{session['id']}/artifacts/export-markdown").raise_for_status()
    print("exported markdown")
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Update runtime adapter README**

Append to `agent/runtime-adapters/README.md`:

```markdown
## Phase 3 Runtime Selection

`services/api` selects runtime adapters through `DOCAGENT_RUNTIME`.

- `mock`: deterministic local and CI adapter.
- `openhands`: OpenHands Agent Server / SDK adapter.

Runtime-specific payloads must stay inside their adapter package. The product backend consumes `RuntimeOperationResult`, semantic timeline events, raw event references, and stable session states.
```

- [ ] **Step 3: Update API README**

Append to `services/api/README.md`:

```markdown
## Runtime Configuration

Default:

```powershell
$env:DOCAGENT_RUNTIME = "mock"
```

OpenHands opt-in:

```powershell
$env:DOCAGENT_RUNTIME = "openhands"
$env:OPENHANDS_BASE_URL = "http://127.0.0.1:8001"
```

Normal CI and local development should keep `mock` unless OpenHands Agent Server is installed and running.
```
```

- [ ] **Step 4: Update testing docs**

Append to `docs/quality/testing.md`:

```markdown
## Phase 3 Runtime Adapter

Run runtime adapter tests:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest packages/contracts/tests packages/timeline/tests services/api/tests agent/runtime-adapters/mock/tests agent/runtime-adapters/openhands/tests -q
```

OpenHands smoke is opt-in:

```powershell
$env:DOCAGENT_RUNTIME = "openhands"
$env:OPENHANDS_BASE_URL = "http://127.0.0.1:8001"
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tools/runtime/openhands_smoke.py
```
```

- [ ] **Step 5: Run documentation structure check**

Run:

```powershell
Get-ChildItem -Recurse -File | Select-Object FullName
```

Expected: output includes `tools/runtime/openhands_smoke.py` and this plan file.

- [ ] **Step 6: Commit Task 9**

Run:

```powershell
git add tools/runtime/openhands_smoke.py agent/runtime-adapters/README.md services/api/README.md docs/quality/testing.md
git commit -m "Document Phase 3 runtime adapter setup"
```

## Task 10: Final Verification And Plan Update

**Files:**
- Modify: `docs/exec-plans/active/2026-05-06-phase-3-openhands-runtime-adapter.md`

- [ ] **Step 1: Run full Python verification**

Run:

```powershell
& 'C:\Users\fai_l\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest packages/contracts/tests packages/workspace/tests packages/timeline/tests tools/import/tests services/api/tests agent/runtime-adapters/mock/tests agent/runtime-adapters/openhands/tests tests -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend build**

Run:

```powershell
cd apps/web
npm run build
```

Expected: PASS.

- [ ] **Step 3: Confirm API no longer imports mock directly**

Run:

```powershell
Select-String -Path services/api/docagent_api/app.py -Pattern "docagent_mock_runtime|MockRuntimeAdapter"
```

Expected: no output.

- [ ] **Step 4: Confirm raw events path is available**

Run:

```powershell
Select-String -Path services/api/docagent_api/state.py -Pattern "raw-events|append_raw_runtime_event"
```

Expected: output includes both strings.

- [ ] **Step 5: Mark execution readiness**

Add near the top of this plan:

```markdown
**Execution readiness:** Phase 3 runtime adapter tests, full Python verification, and frontend build pass locally.
```

- [ ] **Step 6: Commit final plan update**

Run:

```powershell
git add docs/exec-plans/active/2026-05-06-phase-3-openhands-runtime-adapter.md
git commit -m "Verify Phase 3 runtime adapter implementation"
```

## Self-Review

Spec coverage:

- Adapter boundary: Tasks 1, 4, 5, and 8.
- OpenHands isolation: Task 6.
- State machine: Tasks 2 and 8.
- Streaming and raw event storage: Tasks 2, 6, 7, and 8.
- Prompt assembly ownership: Task 3.
- Timeout/cancel baseline: Tasks 1, 2, 6, and 8.
- Explicit API demo path and docs: Task 9.
- `utc_now()` shared cleanup: Task 1.

Placeholder scan:

- The plan intentionally keeps real OpenHands SDK variation isolated in `client.py`.
- No task uses placeholder markers or unspecified implementation steps.

Type consistency:

- `RuntimeOperationResult`, `PromptBundle`, and `RawRuntimeEvent` are defined before adapter use.
- Session states use `RuntimeSessionState` everywhere.
- Raw event storage uses JSONL and semantic timeline uses `raw_event_id` references.
