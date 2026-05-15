from __future__ import annotations

import os
from threading import Thread
import time
from typing import Any, Protocol
from uuid import uuid4

from docagent_contracts import PromptBundle


class OpenHandsClient(Protocol):
    def create_session(self, prompt_bundle: PromptBundle) -> str:
        ...

    def has_conversation(self, runtime_session_id: str) -> bool:
        ...

    def send_message(self, runtime_session_id: str, message: str) -> list[dict[str, Any]]:
        ...

    def send_message_stream(self, runtime_session_id: str, message: str) -> Any:
        ...

    def cancel_session(self, runtime_session_id: str) -> list[dict[str, Any]]:
        ...

    def answer_permission(self, runtime_session_id: str, request_id: str, decision: str) -> list[dict[str, Any]]:
        ...


class OpenHandsAgentServerClient:
    def __init__(self, base_url: str | None = None, timeout_seconds: int = 900) -> None:
        self.base_url = (
            base_url
            or os.environ.get("DOCAGENT_ACP_RUNTIME_URL")
            or os.environ.get("OPENHANDS_BASE_URL")
        )
        self.timeout_seconds = timeout_seconds
        self._conversations: dict[str, Any] = {}

    def create_session(self, prompt_bundle: PromptBundle) -> str:
        if not self.base_url:
            raise RuntimeError(
                "DOCAGENT_ACP_RUNTIME_URL is required when using DOCAGENT_RUNTIME=openhands-acp. "
                "OPENHANDS_BASE_URL remains a temporary compatibility fallback."
            )
        api_key = os.environ.get("LLM_API_KEY")
        if not api_key:
            raise RuntimeError("LLM_API_KEY is required when using DOCAGENT_RUNTIME=openhands-acp.")

        try:
            from openhands.sdk import LLM, Conversation, Workspace
            from openhands.tools.preset.default import get_default_agent
        except ImportError as exc:
            raise RuntimeError(
                "OpenHands SDK packages are required. Install openhands-sdk, openhands-tools, "
                "openhands-workspace, and openhands-agent-server."
            ) from exc

        llm = LLM(
            usage_id="docagent",
            model=os.environ.get("LLM_MODEL", "anthropic/claude-sonnet-4-5-20250929"),
            base_url=os.environ.get("LLM_BASE_URL"),
            api_key=api_key,
        )
        agent = get_default_agent(llm=llm, cli_mode=True)
        workspace = Workspace(host=self.base_url, working_dir=str(prompt_bundle.workspace_root))
        conversation = Conversation(agent=agent, workspace=workspace)
        runtime_session_id = str(getattr(conversation.state, "id", None) or uuid4().hex)
        self._conversations[runtime_session_id] = conversation
        return runtime_session_id

    def has_conversation(self, runtime_session_id: str) -> bool:
        return runtime_session_id in self._conversations

    def send_message(self, runtime_session_id: str, message: str) -> list[dict[str, Any]]:
        conversation = self._conversation(runtime_session_id)
        before_count = len(getattr(conversation.state, "events", []))
        conversation.send_message(message)
        conversation.run()
        events = getattr(conversation.state, "events", [])[before_count:]
        return [_event_to_payload(event) for event in events]

    def send_message_stream(
        self,
        runtime_session_id: str,
        message: str,
        poll_interval_seconds: float = 0.1,
    ) -> Any:
        conversation = self._conversation(runtime_session_id)
        before_count = len(getattr(conversation.state, "events", []))
        error: list[BaseException] = []

        conversation.send_message(message)

        def run() -> None:
            try:
                conversation.run()
            except BaseException as exc:
                error.append(exc)

        worker = Thread(target=run, daemon=True)
        worker.start()
        next_index = before_count
        while worker.is_alive():
            events = getattr(conversation.state, "events", [])
            while next_index < len(events):
                yield _event_to_payload(events[next_index])
                next_index += 1
            time.sleep(poll_interval_seconds)

        worker.join()
        events = getattr(conversation.state, "events", [])
        while next_index < len(events):
            yield _event_to_payload(events[next_index])
            next_index += 1
        if error:
            raise error[0]

    def cancel_session(self, runtime_session_id: str) -> list[dict[str, Any]]:
        conversation = self._conversation(runtime_session_id)
        close = getattr(conversation, "close", None)
        if callable(close):
            close()
        self._conversations.pop(runtime_session_id, None)
        return [{"kind": "cancelled"}]

    def answer_permission(self, runtime_session_id: str, request_id: str, decision: str) -> list[dict[str, Any]]:
        conversation = self._conversation(runtime_session_id)
        # Temporary OpenHands ACP shim: the permission API is probed at call time
        # while SDK method names settle across OpenHands releases.
        answer = getattr(conversation, "answer_permission", None)
        if callable(answer):
            result = answer(request_id, decision)
            return [_event_to_payload(event) for event in (result or [])]
        raise NotImplementedError("OpenHands client does not expose permission response forwarding yet.")

    def _conversation(self, runtime_session_id: str) -> Any:
        try:
            return self._conversations[runtime_session_id]
        except KeyError as exc:
            raise RuntimeError(
                "OpenHands Agent Server client does not support cross-process resume "
                f"for runtime session {runtime_session_id}; the conversation is not present in this process."
            ) from exc


def _event_to_payload(event: Any) -> dict[str, Any]:
    if isinstance(event, dict):
        payload = dict(event)
    elif hasattr(event, "model_dump"):
        payload = event.model_dump(mode="json")
    elif hasattr(event, "dict"):
        payload = event.dict()
    else:
        payload = {"repr": repr(event)}
    payload.setdefault("kind", type(event).__name__)
    path = _extract_path(payload)
    if path:
        payload["path"] = path
    return payload


def _extract_path(payload: dict[str, Any]) -> str | None:
    for key in ("path", "file_path", "filename"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    for value in payload.values():
        if isinstance(value, dict):
            nested = _extract_path(value)
            if nested:
                return nested
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    nested = _extract_path(item)
                    if nested:
                        return nested
    return None
