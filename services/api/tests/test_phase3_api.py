from pathlib import Path

from fastapi.testclient import TestClient

from docagent_api.app import create_app


def test_invalid_outline_approval_returns_409(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build onboarding analytics"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    response = client.post(
        f"/sessions/{session['id']}/outline/approve",
        json={"outline_markdown": "# Outline\n"},
    )

    assert response.status_code == 409
    assert "Cannot transition session" in response.json()["detail"]


def test_cancel_running_session_returns_cancelled(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build onboarding analytics"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    client.post(f"/sessions/{session['id']}/loop/start")

    response = client.post(f"/sessions/{session['id']}/cancel")

    assert response.status_code == 200
    assert response.json()["next_state"] == "cancelled"
    assert client.get(f"/sessions/{session['id']}").json()["status"] == "cancelled"
