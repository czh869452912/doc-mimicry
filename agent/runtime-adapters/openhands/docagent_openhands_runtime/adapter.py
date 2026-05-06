from __future__ import annotations

from typing import Any
from uuid import uuid4

from docagent_contracts import (
    PromptBundle,
    RawRuntimeEvent,
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

    def create_session(self, session_id: str, prompt_bundle: PromptBundle) -> RuntimeOperationResult:
        runtime_session_id = self.client.create_session(prompt_bundle)
        self._runtime_session_ids[session_id] = runtime_session_id
        self._states[session_id] = RuntimeSessionState.IDLE
        return RuntimeOperationResult(
            session_id=session_id,
            next_state=RuntimeSessionState.IDLE,
            raw_events=[
                self._raw_event(
                    session_id,
                    runtime_session_id,
                    "session_created",
                    {"workspace_root": str(prompt_bundle.workspace_root), "doc_type_id": prompt_bundle.doc_type_id},
                )
            ],
        )

    def send_message(self, session_id: str, message: str) -> RuntimeOperationResult:
        raw_payloads = self.client.send_message(self._runtime_session_id(session_id), message)
        next_state = RuntimeSessionState.DRAFT_READY
        self._states[session_id] = next_state
        return self._result(session_id, next_state, raw_payloads)

    def start_loop(self, session_id: str) -> RuntimeOperationResult:
        raw_payloads = self.client.send_message(
            self._runtime_session_id(session_id),
            "Build context files and propose an outline. Stop when outline approval is required.",
        )
        next_state = RuntimeSessionState.AWAIT_OUTLINE_APPROVAL
        self._states[session_id] = next_state
        return self._result(session_id, next_state, raw_payloads)

    def approve_outline(self, session_id: str) -> RuntimeOperationResult:
        raw_payloads = self.client.send_message(
            self._runtime_session_id(session_id),
            "The outline is approved. Generate the draft in Markdown.",
        )
        next_state = RuntimeSessionState.DRAFT_READY
        self._states[session_id] = next_state
        return self._result(session_id, next_state, raw_payloads)

    def revise_selection(self, session_id: str, selection: str, instruction: str) -> RuntimeOperationResult:
        raw_payloads = self.client.send_message(
            self._runtime_session_id(session_id),
            f"Revise this selected text according to the instruction.\n\nSelection:\n{selection}\n\nInstruction:\n{instruction}",
        )
        next_state = RuntimeSessionState.DRAFT_READY
        self._states[session_id] = next_state
        return self._result(session_id, next_state, raw_payloads)

    def run_checklist(self, session_id: str) -> RuntimeOperationResult:
        raw_payloads = self.client.send_message(
            self._runtime_session_id(session_id),
            "Run the document type checklist and write reviews/checklist_result.md.",
        )
        next_state = RuntimeSessionState.DRAFT_READY
        self._states[session_id] = next_state
        return self._result(session_id, next_state, raw_payloads)

    def export_markdown(self, session_id: str) -> RuntimeOperationResult:
        raw_payloads = self.client.send_message(
            self._runtime_session_id(session_id),
            "Export the current draft to artifacts/prd-draft.md.",
        )
        next_state = RuntimeSessionState.COMPLETED
        self._states[session_id] = next_state
        return self._result(session_id, next_state, raw_payloads)

    def cancel(self, session_id: str) -> RuntimeOperationResult:
        raw_payloads = self.client.cancel_session(self._runtime_session_id(session_id))
        next_state = RuntimeSessionState.CANCELLED
        self._states[session_id] = next_state
        return self._result(session_id, next_state, raw_payloads)

    def get_state(self, session_id: str) -> RuntimeSessionState:
        return self._states[session_id]

    def _result(
        self,
        session_id: str,
        next_state: RuntimeSessionState,
        raw_payloads: list[dict[str, Any]],
    ) -> RuntimeOperationResult:
        runtime_session_id = self._runtime_session_id(session_id)
        raw_events = [
            self._raw_event(
                session_id,
                runtime_session_id,
                payload.get("kind", payload.get("type", "event")),
                payload,
            )
            for payload in raw_payloads
        ]
        return RuntimeOperationResult(
            session_id=session_id,
            next_state=next_state,
            changed_paths=[str(event.payload["path"]) for event in raw_events if "path" in event.payload],
            raw_events=raw_events,
        )

    def _runtime_session_id(self, session_id: str) -> str:
        try:
            return self._runtime_session_ids[session_id]
        except KeyError as exc:
            raise RuntimeError(
                f"OpenHands runtime session is not bound for {session_id}. Create a new session."
            ) from exc

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
