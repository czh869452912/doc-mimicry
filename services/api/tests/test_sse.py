from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from docagent_api.app import create_app


@pytest.fixture(autouse=True)
def _short_sse_polls(monkeypatch: pytest.MonkeyPatch) -> None:
    # Bound the SSE generator so the in-process test client can finish reading
    # the response body within the test (in-process ASGI buffers the full body).
    monkeypatch.setenv("DOCAGENT_SSE_MAX_POLLS", "1")
    monkeypatch.setenv("DOCAGENT_SSE_POLL_INTERVAL", "0.05")


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))


def test_stream_timeline_unknown_session_returns_404(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.get("/sessions/no-such-session/timeline/stream")
    assert response.status_code == 404


def test_stream_timeline_returns_sse_content_type(tmp_path: Path) -> None:
    client = _client(tmp_path)
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "SSE test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    with client.stream("GET", f"/sessions/{session['id']}/timeline/stream") as r:
        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]


def test_stream_timeline_sends_existing_events(tmp_path: Path) -> None:
    import json

    client = _client(tmp_path)
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "SSE events test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    session_id = session["id"]

    # Run start_loop synchronously to populate the timeline
    client.post(f"/sessions/{session_id}/loop/start")

    data_lines: list[str] = []
    with client.stream("GET", f"/sessions/{session_id}/timeline/stream") as r:
        assert r.status_code == 200
        for line in r.iter_lines():
            line = line.strip()
            if line.startswith("data:"):
                data_lines.append(line[len("data:"):].strip())

    assert data_lines, "expected at least one data line"
    event = json.loads(data_lines[0])
    assert "id" in event
    assert "kind" in event
