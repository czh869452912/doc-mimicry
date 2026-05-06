import os

import pytest

from docagent_openhands_runtime.client import OpenHandsAgentServerClient, _event_to_payload


def test_openhands_client_requires_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENHANDS_BASE_URL", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "test-key")

    with pytest.raises(RuntimeError, match="OPENHANDS_BASE_URL"):
        OpenHandsAgentServerClient().create_session(None)  # type: ignore[arg-type]


def test_openhands_client_requires_llm_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENHANDS_BASE_URL", "http://127.0.0.1:8001")
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        OpenHandsAgentServerClient().create_session(None)  # type: ignore[arg-type]


def test_event_to_payload_extracts_nested_path() -> None:
    class Event:
        def model_dump(self, mode: str) -> dict[str, object]:
            return {"tool_call": {"args": {"path": "draft/outline.md"}}}

    payload = _event_to_payload(Event())

    assert payload["kind"] == "Event"
    assert payload["path"] == "draft/outline.md"
