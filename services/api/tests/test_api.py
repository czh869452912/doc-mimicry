from pathlib import Path
import os

from fastapi.testclient import TestClient

from docagent_api.app import create_app
from docagent_api.app import state_root_from_env


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


def test_task_creation_keeps_title_separate_from_description(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))

    response = client.post(
        "/tasks",
        json={
            "doc_type_id": "prd",
            "title": "Billing controls PRD",
            "description": "Write a PRD for enterprise billing controls.",
        },
    )

    assert response.status_code == 200
    task = response.json()
    assert task["title"] == "Billing controls PRD"
    assert task["description"] == "Write a PRD for enterprise billing controls."
    assert task["brief"] == "Write a PRD for enterprise billing controls."


def test_state_root_can_be_read_from_environment(tmp_path: Path) -> None:
    state_root = tmp_path / "custom-state"
    original = os.environ.get("DOCAGENT_STATE_ROOT")
    os.environ["DOCAGENT_STATE_ROOT"] = str(state_root)
    try:
        assert state_root_from_env() == state_root
    finally:
        if original is None:
            os.environ.pop("DOCAGENT_STATE_ROOT", None)
        else:
            os.environ["DOCAGENT_STATE_ROOT"] = original
