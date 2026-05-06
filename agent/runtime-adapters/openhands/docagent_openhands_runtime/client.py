from __future__ import annotations

from typing import Any, Protocol

from docagent_contracts import PromptBundle


class OpenHandsClient(Protocol):
    def create_session(self, prompt_bundle: PromptBundle) -> str:
        ...

    def send_message(self, runtime_session_id: str, message: str) -> list[dict[str, Any]]:
        ...

    def cancel_session(self, runtime_session_id: str) -> list[dict[str, Any]]:
        ...


class OpenHandsAgentServerClient:
    def __init__(self, base_url: str | None = None, timeout_seconds: int = 900) -> None:
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    def create_session(self, prompt_bundle: PromptBundle) -> str:
        raise NotImplementedError("Install/configure the OpenHands agent server client before using DOCAGENT_RUNTIME=openhands.")

    def send_message(self, runtime_session_id: str, message: str) -> list[dict[str, Any]]:
        raise NotImplementedError("OpenHands agent server streaming is not configured yet.")

    def cancel_session(self, runtime_session_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError("OpenHands agent server cancellation is not configured yet.")
