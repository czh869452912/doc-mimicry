import os
from threading import Event

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


def test_openhands_client_unknown_conversation_explains_resume_gap() -> None:
    client = OpenHandsAgentServerClient(base_url="http://example.test")

    with pytest.raises(RuntimeError, match="does not support cross-process resume"):
        client.send_message("missing-runtime-id", "hello")


def test_openhands_client_streams_events_while_run_blocks() -> None:
    class State:
        def __init__(self) -> None:
            self.events: list[object] = []

    class Conversation:
        def __init__(self) -> None:
            self.state = State()
            self.started = Event()
            self.finish = Event()

        def send_message(self, message: str) -> None:
            self.state.events.append({"kind": "user", "content": message})

        def run(self) -> None:
            self.state.events.append({"kind": "agent", "content": "partial"})
            self.started.set()
            assert self.finish.wait(timeout=2)
            self.state.events.append({"kind": "file_written", "path": "draft/final.md"})

    client = OpenHandsAgentServerClient(base_url="http://example.test")
    conversation = Conversation()
    client._conversations["runtime-001"] = conversation

    stream = client.send_message_stream("runtime-001", "hello", poll_interval_seconds=0.01)
    first = next(stream)
    assert first["kind"] == "user"

    assert conversation.started.wait(timeout=2)
    second = next(stream)
    assert second["kind"] == "agent"

    conversation.finish.set()
    remaining = list(stream)
    assert remaining[-1]["path"] == "draft/final.md"
