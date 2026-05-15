from __future__ import annotations

from typing import Any
from uuid import uuid4

from docagent_contracts import (
    AcpRuntimeUpdate,
    PromptBundle,
    RawRuntimeEvent,
    RuntimeEventSink,
    RuntimeKind,
    RuntimeOperationResult,
    RuntimeSessionState,
)
from docagent_contracts.time import utc_now

from .client import OpenHandsClient


HOUSEKEEPING_KINDS = {
    "ConversationStateUpdateEvent",
    "ObservationEvent",
    "SystemPromptEvent",
    "session_created",
}


def map_openhands_payload_to_acp_update(session_id: str, payload: dict[str, Any]) -> AcpRuntimeUpdate | None:
    kind = str(payload.get("kind") or payload.get("type") or "event")
    if kind in HOUSEKEEPING_KINDS:
        return None
    if kind == "ConversationErrorEvent":
        detail = str(payload.get("detail") or payload.get("message") or "Runtime error")
        code = payload.get("code")
        summary = f"Agent error ({code}): {detail}" if code else detail
        return AcpRuntimeUpdate(
            session_id=session_id,
            event_type="runtime/error",
            payload=payload,
            projection={
                "timeline_kind": "error",
                "actor": "system",
                "summary": summary[:240],
                "paths": [],
                "status": "failed",
            },
        )
    if kind == "MessageEvent":
        text = _message_event_text(payload)
        if not text:
            return None
        return AcpRuntimeUpdate(
            session_id=session_id,
            event_type="message_delta",
            payload={
                "role": "assistant",
                "content": text,
                "message_id": str(payload.get("id") or payload.get("message_id") or "openhands-message"),
                "raw": payload,
            },
        )
    if kind == "ActionEvent":
        action = payload.get("action") if isinstance(payload.get("action"), dict) else {}
        action_kind = str(action.get("kind") or payload.get("tool_name") or "tool")
        if action_kind in {"ThinkAction", "FinishAction"}:
            return None
        path = payload.get("path") or action.get("path") or action.get("file_path")
        if path:
            path = str(path)
            return AcpRuntimeUpdate(
                session_id=session_id,
                event_type="file/write",
                payload={**payload, "path": path},
                projection={
                    "timeline_kind": "update_draft",
                    "actor": "tool",
                    "summary": f"Write {path}",
                    "paths": [path],
                    "status": "succeeded",
                },
            )
        return AcpRuntimeUpdate(
            session_id=session_id,
            event_type="tool/call",
            payload={
                "name": action_kind,
                "status": "succeeded",
                "raw": payload,
            },
            projection={
                "timeline_kind": "agent_tool_call",
                "actor": "tool",
                "summary": _tool_summary(action_kind, action),
                "paths": [],
                "status": "succeeded",
            },
        )
    if kind in {"file_written", "file_write", "write_file"}:
        path = payload.get("path")
        paths = [str(path)] if path else []
        return AcpRuntimeUpdate(
            session_id=session_id,
            event_type="file/write",
            payload=payload,
            projection={
                "timeline_kind": "update_draft",
                "actor": "tool",
                "summary": f"Write {path}" if path else "File write",
                "paths": paths,
                "status": "succeeded",
            },
        )
    if kind in {"message", "agent_message"}:
        return AcpRuntimeUpdate(
            session_id=session_id,
            event_type="message_delta",
            payload={
                "role": "assistant",
                "content": str(payload.get("content") or payload.get("message") or ""),
                "message_id": str(payload.get("id") or payload.get("message_id") or "openhands-message"),
                "raw": payload,
            },
        )
    if kind == "cancelled":
        return AcpRuntimeUpdate(
            session_id=session_id,
            event_type="session/cancelled",
            payload=payload,
            projection={
                "timeline_kind": "session_status",
                "actor": "system",
                "summary": "Runtime session cancelled",
                "paths": [],
                "status": "cancelled",
            },
        )
    return AcpRuntimeUpdate(
        session_id=session_id,
        event_type=f"openhands/{kind}",
        payload=payload,
    )


def _message_event_text(payload: dict[str, Any]) -> str:
    if payload.get("source") not in {None, "agent"}:
        return ""
    llm_message = payload.get("llm_message")
    if not isinstance(llm_message, dict):
        return ""
    parts = llm_message.get("content")
    if isinstance(parts, str):
        return parts.strip()
    if not isinstance(parts, list):
        return ""
    text_parts = [
        str(part.get("text")).strip()
        for part in parts
        if isinstance(part, dict) and part.get("type") == "text" and part.get("text")
    ]
    return "\n".join(part for part in text_parts if part)


def _tool_summary(action_kind: str, action: dict[str, Any]) -> str:
    if action_kind == "TaskTrackerAction":
        command = action.get("command")
        if command == "plan":
            return f"Updating task list ({len(action.get('task_list') or [])} tasks)"
        return "Checking task list"
    return action_kind


def _next_state_for_prompt_action(action: object) -> RuntimeSessionState:
    return {
        "start_loop": RuntimeSessionState.AWAIT_OUTLINE_APPROVAL,
        "approve_outline": RuntimeSessionState.DRAFT_READY,
        "revise_selection": RuntimeSessionState.DRAFT_READY,
        "run_checklist": RuntimeSessionState.DRAFT_READY,
        "export_markdown": RuntimeSessionState.COMPLETED,
        "send_message": RuntimeSessionState.DRAFT_READY,
    }.get(str(action or "send_message"), RuntimeSessionState.DRAFT_READY)


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

    def send_prompt(
        self,
        session_id: str,
        prompt: str,
        metadata: dict[str, Any] | None = None,
    ) -> RuntimeOperationResult:
        runtime_session_id, creation_event = self._ensure_runtime_session(session_id)
        raw_payloads = self.client.send_message(runtime_session_id, prompt)
        action = (metadata or {}).get("action")
        next_state = _next_state_for_prompt_action(action)
        self._states[session_id] = next_state
        acp_updates = [
            update
            for event in [creation_event]
            if event is not None
            for update in [map_openhands_payload_to_acp_update(session_id, {**event.payload, "kind": event.kind})]
            if update is not None
        ]
        acp_updates.extend(
            update
            for payload in raw_payloads
            for update in [map_openhands_payload_to_acp_update(session_id, payload)]
            if update is not None
        )
        return RuntimeOperationResult(
            session_id=session_id,
            next_state=next_state,
            changed_paths=[str(payload["path"]) for payload in raw_payloads if "path" in payload],
            raw_events=[creation_event] if creation_event is not None else [],
            acp_updates=acp_updates,
        )

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

    def stream_updates(self, session_id: str) -> list[AcpRuntimeUpdate]:
        self._runtime_session_id(session_id)
        return []

    def answer_permission(
        self,
        session_id: str,
        request_id: str,
        decision: str,
    ) -> RuntimeOperationResult:
        runtime_session_id = self._runtime_session_id(session_id)
        raw_payloads = self.client.answer_permission(runtime_session_id, request_id, decision)
        next_state = self._states.get(session_id, RuntimeSessionState.IDLE)
        return self._result(session_id, next_state, raw_payloads)

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
