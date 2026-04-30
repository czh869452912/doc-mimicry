from pathlib import Path

from fastapi.testclient import TestClient

from docagent_api.app import create_app


def test_health_endpoint(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_doc_type_endpoints(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))

    listing = client.get("/doc-types")
    detail = client.get("/doc-types/prd")

    assert listing.status_code == 200
    assert listing.json()[0]["id"] == "prd"
    assert detail.status_code == 200
    assert detail.json()["id"] == "prd"
    assert "skill_markdown" in detail.json()


def test_task_session_message_timeline_and_draft_roundtrip(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))

    task_response = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build billing controls"})
    assert task_response.status_code == 200
    task = task_response.json()

    session_response = client.post(f"/tasks/{task['id']}/sessions")
    assert session_response.status_code == 200
    session = session_response.json()

    message_response = client.post(
        f"/sessions/{session['id']}/messages",
        json={"message": "Start the PRD"},
    )
    assert message_response.status_code == 200
    assert message_response.json()["event_count"] == 6

    timeline = client.get(f"/sessions/{session['id']}/timeline").json()
    assert [event["kind"] for event in timeline] == [
        "user_message",
        "read_skill",
        "extract_style",
        "extract_structure",
        "generate_outline",
        "update_draft",
    ]

    draft = client.get(f"/tasks/{task['id']}/draft").json()
    assert "# PRD Draft" in draft["markdown"]

    update_response = client.put(f"/tasks/{task['id']}/draft", json={"markdown": "# Edited\n"})
    assert update_response.status_code == 200
    assert client.get(f"/tasks/{task['id']}/draft").json()["markdown"] == "# Edited\n"
