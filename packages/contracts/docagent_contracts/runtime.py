from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Protocol


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
    RUNNING_CHAT = "running_chat"
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
    workspace_root: Path
    doc_type_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RawRuntimeEvent:
    id: str
    session_id: str
    runtime: RuntimeKind
    runtime_session_id: str
    kind: str
    payload: dict[str, Any]
    created_at: str


@dataclass(frozen=True)
class AcpRuntimeUpdate:
    session_id: str
    event_type: str
    payload: dict[str, Any]
    projection: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeOperationResult:
    session_id: str
    next_state: RuntimeSessionState
    events: list[Any] = field(default_factory=list)
    changed_paths: list[str] = field(default_factory=list)
    raw_events: list[RawRuntimeEvent] = field(default_factory=list)
    acp_updates: list[AcpRuntimeUpdate] = field(default_factory=list)


RuntimeEventSink = Callable[[RawRuntimeEvent], None]


class LegacyRuntimeAdapter(Protocol):
    def create_session(self, session_id: str, prompt_bundle: PromptBundle) -> RuntimeOperationResult:
        ...

    def send_message(self, session_id: str, message: str) -> RuntimeOperationResult:
        ...

    def start_loop(self, session_id: str) -> RuntimeOperationResult:
        ...

    def approve_outline(self, session_id: str) -> RuntimeOperationResult:
        ...

    def revise_selection(self, session_id: str, selection: str, instruction: str) -> RuntimeOperationResult:
        ...

    def run_checklist(self, session_id: str) -> RuntimeOperationResult:
        ...

    def export_markdown(self, session_id: str) -> RuntimeOperationResult:
        ...

    def cancel(self, session_id: str) -> RuntimeOperationResult:
        ...

    def get_state(self, session_id: str) -> RuntimeSessionState:
        ...


class AcpRuntimeAdapter(Protocol):
    def create_session(self, session_id: str, prompt_bundle: PromptBundle) -> RuntimeOperationResult:
        ...

    def send_prompt(
        self,
        session_id: str,
        prompt: str,
        metadata: dict[str, Any] | None = None,
    ) -> RuntimeOperationResult:
        ...

    def stream_updates(self, session_id: str) -> list[AcpRuntimeUpdate]:
        ...

    def cancel(self, session_id: str) -> RuntimeOperationResult:
        ...


RuntimeAdapter = AcpRuntimeAdapter | LegacyRuntimeAdapter
