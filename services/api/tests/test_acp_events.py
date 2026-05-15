from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from docagent_api.app import create_app
from docagent_api.state import DocAgentState

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def _short_sse_polls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCAGENT_SSE_MAX_POLLS", "1")
    monkeypatch.setenv("DOCAGENT_SSE_POLL_INTERVAL", "0.05")


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(state_root=tmp_path / "state", repo_root=REPO_ROOT))


def test_get_acp_events_returns_session_scoped_envelopes(tmp_path: Path) -> None:
    client = _client(tmp_path)
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "ACP events"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    other_session = client.post(f"/tasks/{task['id']}/sessions").json()
    state = DocAgentState(tmp_path / "state")
    stored = state.append_acp_event(
        session["id"],
        {"method": "session/update", "params": {"delta": "Hello"}},
        projection={"timeline_kind": "agent_message"},
    )
    state.append_acp_event(
        other_session["id"],
        {"method": "session/update", "params": {"delta": "Other"}},
    )

    response = client.get(f"/sessions/{session['id']}/events")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": stored["id"],
            "session_id": session["id"],
            "sequence": stored["sequence"],
            "event_type": "session/update",
            "payload": {"method": "session/update", "params": {"delta": "Hello"}},
            "projection": {"timeline_kind": "agent_message"},
            "created_at": stored["created_at"],
        }
    ]


def test_get_acp_events_unknown_session_returns_404(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/sessions/no-such-session/events")

    assert response.status_code == 404


def test_stream_acp_events_sends_sse_ids_and_honors_last_event_id(tmp_path: Path) -> None:
    client = _client(tmp_path)
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "ACP SSE events"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    state = DocAgentState(tmp_path / "state")
    first = state.append_acp_event(
        session["id"],
        {"method": "session/update", "params": {"delta": "First"}},
    )
    second = state.append_acp_event(
        session["id"],
        {"method": "tool/call", "params": {"name": "write_file"}},
    )

    with client.stream("GET", f"/sessions/{session['id']}/events/stream") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        lines = [line.strip() for line in response.iter_lines() if line.strip()]

    assert f"id: {first['sequence']}" in lines
    assert f"id: {second['sequence']}" in lines

    resumed_data_lines: list[str] = []
    resumed_id_lines: list[str] = []
    with client.stream(
        "GET",
        f"/sessions/{session['id']}/events/stream",
        headers={"Last-Event-ID": str(first["sequence"])},
    ) as response:
        assert response.status_code == 200
        for line in response.iter_lines():
            line = line.strip()
            if line.startswith("id:"):
                resumed_id_lines.append(line)
            if line.startswith("data:"):
                resumed_data_lines.append(line.removeprefix("data:").strip())

    assert resumed_id_lines == [f"id: {second['sequence']}"]
    assert [json.loads(line)["id"] for line in resumed_data_lines] == [second["id"]]


def test_prompt_records_user_prompt_without_requiring_timeline_projection(tmp_path: Path) -> None:
    client = _client(tmp_path)
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Use ACP"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    response = client.post(f"/sessions/{session['id']}/messages", json={"message": "Hello"}, params={"background": False})

    assert response.status_code == 200
    acp_events = client.get(f"/sessions/{session['id']}/events").json()
    assert any(
        event["event_type"] == "docagent/prompt"
        and event["payload"]["prompt"] == "Hello"
        for event in acp_events
    )


def test_acp_events_are_session_scoped(tmp_path: Path) -> None:
    client = _client(tmp_path)
    task_one = client.post("/tasks", json={"doc_type_id": "prd", "brief": "One"}).json()
    task_two = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Two"}).json()
    session_one = client.post(f"/tasks/{task_one['id']}/sessions").json()
    session_two = client.post(f"/tasks/{task_two['id']}/sessions").json()

    client.post(f"/sessions/{session_one['id']}/messages", json={"message": "Only one"})

    events_one = client.get(f"/sessions/{session_one['id']}/events").json()
    events_two = client.get(f"/sessions/{session_two['id']}/events").json()

    assert any(event["payload"].get("prompt") == "Only one" for event in events_one)
    assert all(event["payload"].get("prompt") != "Only one" for event in events_two)
