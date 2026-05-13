from __future__ import annotations

from typing import Any
from uuid import uuid4

from docagent_contracts import (
    PromptBundle,
    RawRuntimeEvent,
    RuntimeEventSink,
    RuntimeKind,
    RuntimeOperationResult,
    RuntimeSessionState,
)
from docagent_contracts.time import utc_now

from .client import OpenHandsClient


class OpenHandsRuntimeAdapter:
    def __init__(self, client: OpenHandsClient) -> None:
        self.client = client
        self._runtime_session_ids: dict[str, str] = {}
        self._states: dict[str, RuntimeSessionState] = {}
        self._prompt_bundles: dict[str, PromptBundle] = {}

    def create_session(self, session_id: str, prompt_bundle: PromptBundle) -> RuntimeOperationResult:
        self._prompt_bundles[session_id] = prompt_bundle
        self._states[session_id] = RuntimeSessionState.IDLE
        return RuntimeOperationResult(
            session_id=session_id,
            next_state=RuntimeSessionState.IDLE,
        )

    def bind_runtime_session(
        self,
        session_id: str,
        runtime_session_id: str,
        state: RuntimeSessionState = RuntimeSessionState.IDLE,
    ) -> None:
        self._runtime_session_ids[session_id] = runtime_session_id
        self._states[session_id] = state

    def send_message(self, session_id: str, message: str) -> RuntimeOperationResult:
        runtime_session_id, creation_event = self._ensure_runtime_session(session_id)
        raw_payloads = self.client.send_message(runtime_session_id, message)
        next_state = RuntimeSessionState.DRAFT_READY
        self._states[session_id] = next_state
        return self._result(session_id, next_state, raw_payloads, creation_event=creation_event)

    def send_message_stream(
        self,
        session_id: str,
        message: str,
        sink: RuntimeEventSink,
    ) -> RuntimeOperationResult:
        runtime_session_id, creation_event = self._ensure_runtime_session(session_id)
        raw_payloads = self.client.send_message_stream(runtime_session_id, message)
        return self._stream_result(session_id, RuntimeSessionState.DRAFT_READY, raw_payloads, sink)

    def start_loop(self, session_id: str) -> RuntimeOperationResult:
        runtime_session_id, creation_event = self._ensure_runtime_session(session_id)
        raw_payloads = self.client.send_message(
            runtime_session_id,
            "Build context files and propose an outline. Stop when outline approval is required.",
        )
        next_state = RuntimeSessionState.AWAIT_OUTLINE_APPROVAL
        self._states[session_id] = next_state
        return self._result(session_id, next_state, raw_payloads, creation_event=creation_event)

    def start_loop_stream(self, session_id: str, sink: RuntimeEventSink) -> RuntimeOperationResult:
        runtime_session_id, creation_event = self._ensure_runtime_session(session_id)
        raw_payloads = self.client.send_message_stream(
            runtime_session_id,
            "Build context files and propose an outline. Stop when outline approval is required.",
        )
        return self._stream_result(
            session_id, RuntimeSessionState.AWAIT_OUTLINE_APPROVAL, raw_payloads, sink,
            creation_event=creation_event,
        )

    def approve_outline(self, session_id: str) -> RuntimeOperationResult:
        runtime_session_id, creation_event = self._ensure_runtime_session(session_id)
        raw_payloads = self.client.send_message(
            runtime_session_id,
            "The outline is approved. Generate the draft in Markdown.",
        )
        next_state = RuntimeSessionState.DRAFT_READY
        self._states[session_id] = next_state
        return self._result(session_id, next_state, raw_payloads, creation_event=creation_event)

    def approve_outline_stream(self, session_id: str, sink: RuntimeEventSink) -> RuntimeOperationResult:
        runtime_session_id, creation_event = self._ensure_runtime_session(session_id)
        raw_payloads = self.client.send_message_stream(
            runtime_session_id,
            "The outline is approved. Generate the draft in Markdown.",
        )
        return self._stream_result(
            session_id, RuntimeSessionState.DRAFT_READY, raw_payloads, sink,
            creation_event=creation_event,
        )

    def revise_selection(self, session_id: str, selection: str, instruction: str) -> RuntimeOperationResult:
        runtime_session_id, creation_event = self._ensure_runtime_session(session_id)
        raw_payloads = self.client.send_message(
            runtime_session_id,
            f"Revise this selected text according to the instruction.\n\nSelection:\n{selection}\n\nInstruction:\n{instruction}",
        )
        next_state = RuntimeSessionState.DRAFT_READY
        self._states[session_id] = next_state
        return self._result(session_id, next_state, raw_payloads, creation_event=creation_event)

    def revise_selection_stream(
        self,
        session_id: str,
        selection: str,
        instruction: str,
        sink: RuntimeEventSink,
    ) -> RuntimeOperationResult:
        runtime_session_id, creation_event = self._ensure_runtime_session(session_id)
        raw_payloads = self.client.send_message_stream(
            runtime_session_id,
            f"Revise this selected text according to the instruction.\n\nSelection:\n{selection}\n\nInstruction:\n{instruction}",
        )
        return self._stream_result(
            session_id, RuntimeSessionState.DRAFT_READY, raw_payloads, sink,
            creation_event=creation_event,
        )

    def run_checklist(self, session_id: str) -> RuntimeOperationResult:
        runtime_session_id, creation_event = self._ensure_runtime_session(session_id)
        raw_payloads = self.client.send_message(
            runtime_session_id,
            "Run the document type checklist and write reviews/checklist_result.md.",
        )
        next_state = RuntimeSessionState.DRAFT_READY
        self._states[session_id] = next_state
        return self._result(session_id, next_state, raw_payloads, creation_event=creation_event)

    def run_checklist_stream(self, session_id: str, sink: RuntimeEventSink) -> RuntimeOperationResult:
        runtime_session_id, creation_event = self._ensure_runtime_session(session_id)
        raw_payloads = self.client.send_message_stream(
            runtime_session_id,
            "Run the document type checklist and write reviews/checklist_result.md.",
        )
        return self._stream_result(
            session_id, RuntimeSessionState.DRAFT_READY, raw_payloads, sink,
            creation_event=creation_event,
        )

    def export_markdown(self, session_id: str) -> RuntimeOperationResult:
        runtime_session_id, creation_event = self._ensure_runtime_session(session_id)
        raw_payloads = self.client.send_message(
            runtime_session_id,
            "Export the current draft to artifacts/prd-draft.md.",
        )
        next_state = RuntimeSessionState.COMPLETED
        self._states[session_id] = next_state
        return self._result(session_id, next_state, raw_payloads, creation_event=creation_event)

    def export_markdown_stream(self, session_id: str, sink: RuntimeEventSink) -> RuntimeOperationResult:
        runtime_session_id, creation_event = self._ensure_runtime_session(session_id)
        raw_payloads = self.client.send_message_stream(
            runtime_session_id,
            "Export the current draft to artifacts/prd-draft.md.",
        )
        return self._stream_result(
            session_id, RuntimeSessionState.COMPLETED, raw_payloads, sink,
            creation_event=creation_event,
        )

    def cancel(self, session_id: str) -> RuntimeOperationResult:
        runtime_session_id = self._runtime_session_ids.get(session_id)
        raw_payloads = self.client.cancel_session(runtime_session_id) if runtime_session_id else [{"kind": "cancelled"}]
        next_state = RuntimeSessionState.CANCELLED
        self._states[session_id] = next_state
        return self._result(session_id, next_state, raw_payloads, allow_unbound=True)

    def get_state(self, session_id: str) -> RuntimeSessionState:
        return self._states[session_id]

    def _result(
        self,
        session_id: str,
        next_state: RuntimeSessionState,
        raw_payloads: list[dict[str, Any]],
        creation_event: RawRuntimeEvent | None = None,
        allow_unbound: bool = False,
    ) -> RuntimeOperationResult:
        runtime_session_id = self._runtime_session_ids.get(session_id) if allow_unbound else self._runtime_session_id(session_id)
        if runtime_session_id is None:
            runtime_session_id = ""
        raw_events = [creation_event] if creation_event is not None else []
        raw_events.extend([
            self._raw_event(
                session_id,
                runtime_session_id,
                payload.get("kind", payload.get("type", "event")),
                payload,
            )
            for payload in raw_payloads
        ])
        return RuntimeOperationResult(
            session_id=session_id,
            next_state=next_state,
            changed_paths=[str(event.payload["path"]) for event in raw_events if "path" in event.payload],
            raw_events=raw_events,
        )

    def _stream_result(
        self,
        session_id: str,
        next_state: RuntimeSessionState,
        raw_payloads: Any,
        sink: RuntimeEventSink,
        creation_event: RawRuntimeEvent | None = None,
    ) -> RuntimeOperationResult:
        runtime_session_id = self._runtime_session_id(session_id)
        if creation_event is not None:
            sink(creation_event)
        changed_paths: list[str] = []
        for payload in raw_payloads:
            raw_event = self._raw_event(
                session_id,
                runtime_session_id,
                payload.get("kind", payload.get("type", "event")),
                payload,
            )
            if "path" in raw_event.payload:
                changed_paths.append(str(raw_event.payload["path"]))
            sink(raw_event)
        self._states[session_id] = next_state
        return RuntimeOperationResult(
            session_id=session_id,
            next_state=next_state,
            changed_paths=changed_paths,
        )

    def _runtime_session_id(self, session_id: str) -> str:
        try:
            return self._runtime_session_ids[session_id]
        except KeyError as exc:
            raise RuntimeError(
                f"OpenHands runtime session is not bound for {session_id}. Create a new session."
            ) from exc

    def _ensure_runtime_session(self, session_id: str) -> tuple[str, RawRuntimeEvent | None]:
        runtime_session_id = self._runtime_session_ids.get(session_id)
        if runtime_session_id:
            return runtime_session_id, None
        try:
            prompt_bundle = self._prompt_bundles[session_id]
        except KeyError as exc:
            raise RuntimeError(
                f"OpenHands runtime session is not bound for {session_id}. Create a new session."
            ) from exc
        runtime_session_id = self.client.create_session(prompt_bundle)
        self._runtime_session_ids[session_id] = runtime_session_id
        return runtime_session_id, self._raw_event(
            session_id,
            runtime_session_id,
            "session_created",
            {"workspace_root": str(prompt_bundle.workspace_root), "doc_type_id": prompt_bundle.doc_type_id},
        )

    def _raw_event(
        self,
        session_id: str,
        runtime_session_id: str,
        kind: str,
        payload: dict[str, Any],
    ) -> RawRuntimeEvent:
        return RawRuntimeEvent(
            id=f"raw-{uuid4().hex[:12]}",
            session_id=session_id,
            runtime=RuntimeKind.OPENHANDS,
            runtime_session_id=runtime_session_id,
            kind=kind,
            payload=payload,
            created_at=utc_now(),
        )
