from pathlib import Path

from fastapi.testclient import TestClient

from docagent_api.app import create_app


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))


def test_create_draft_checkpoint_copies_current_draft_to_versions(tmp_path: Path) -> None:
    client = _client(tmp_path)
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Checkpoint draft"}).json()
    client.put(f"/tasks/{task['id']}/draft", json={"markdown": "# Current draft\n\nBody.\n"})

    response = client.post(
        f"/tasks/{task['id']}/draft/checkpoints",
        json={"note": "Before user revision"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == task["id"]
    assert body["version"] == "v001"
    assert body["version_path"] == "versions/v001.md"
    assert body["source_path"] == "draft/draft.md"
    assert body["summary"] == "Before user revision"
    assert body["created_by"] == "user"
    assert body["created_at"].endswith("Z")
    assert (Path(task["workspace_root"]) / "versions" / "v001.md").read_text(encoding="utf-8") == (
        "# Current draft\n\nBody.\n"
    )


def test_create_draft_checkpoint_requires_existing_draft(tmp_path: Path) -> None:
    client = _client(tmp_path)
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Missing draft"}).json()

    response = client.post(f"/tasks/{task['id']}/draft/checkpoints", json={"note": "No draft yet"})

    assert response.status_code == 400
    assert "draft" in response.json()["detail"].lower()


def test_create_draft_checkpoint_emits_latest_session_timeline_and_acp_event(tmp_path: Path) -> None:
    client = _client(tmp_path)
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Observable checkpoint"}).json()
    older_session = client.post(f"/tasks/{task['id']}/sessions").json()
    latest_session = client.post(f"/tasks/{task['id']}/sessions").json()
    client.put(f"/tasks/{task['id']}/draft", json={"markdown": "# Draft\n"})

    response = client.post(
        f"/tasks/{task['id']}/draft/checkpoints",
        json={"note": "Manual checkpoint"},
    )

    assert response.status_code == 200
    assert client.get(f"/sessions/{older_session['id']}/timeline").json() == []

    timeline = client.get(f"/sessions/{latest_session['id']}/timeline").json()
    assert any(
        event["kind"] == "create_checkpoint"
        and event["actor"] == "user"
        and event["summary"] == "Manual checkpoint"
        and event["paths"] == ["versions/v001.md"]
        for event in timeline
    )
    acp_events = client.get(f"/sessions/{latest_session['id']}/events").json()
    assert any(
        event["event_type"] == "docagent/projection"
        and event["projection"]["timeline_kind"] == "create_checkpoint"
        and event["projection"]["actor"] == "user"
        and event["projection"]["paths"] == ["versions/v001.md"]
        for event in acp_events
    )
