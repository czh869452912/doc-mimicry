from pathlib import Path

from fastapi.testclient import TestClient

from docagent_api.app import create_app


def test_phase2_prd_authoring_loop(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))

    task_response = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build onboarding analytics"})
    assert task_response.status_code == 200
    task = task_response.json()

    session_response = client.post(f"/tasks/{task['id']}/sessions")
    assert session_response.status_code == 200
    session = session_response.json()

    list_response = client.get("/tasks")
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [task["id"]]

    sessions_response = client.get(f"/tasks/{task['id']}/sessions")
    assert sessions_response.status_code == 200
    assert [item["id"] for item in sessions_response.json()] == [session["id"]]

    import_response = client.post(
        f"/tasks/{task['id']}/inputs/text",
        json={"name": "research.txt", "content": "Users need funnel visibility."},
    )
    assert import_response.status_code == 200
    imported = import_response.json()
    assert imported["markdown_path"] == "inputs/markdown/research.md"
    assert imported["conversion_report_path"] == "inputs/reports/research.conversion.json"

    start_response = client.post(f"/sessions/{session['id']}/loop/start")
    assert start_response.status_code == 200
    assert start_response.json()["next_state"] == "await_outline_approval"

    workspace = client.get(f"/tasks/{task['id']}/workspace").json()
    assert "draft/outline.md" in [file["path"] for file in workspace["files"]]
    assert {"path": "inputs/reports/research.conversion.json", "group": "inputs", "kind": "text"} in workspace["files"]

    outline = client.get(f"/tasks/{task['id']}/workspace/files", params={"path": "draft/outline.md"}).json()
    assert "# Outline" in outline["content"]

    approve_response = client.post(
        f"/sessions/{session['id']}/outline/approve",
        json={"outline_markdown": outline["content"]},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["next_state"] == "draft_ready"

    draft = client.get(f"/tasks/{task['id']}/draft").json()["markdown"]
    assert "# PRD Draft" in draft

    revise_response = client.post(
        f"/sessions/{session['id']}/revision/selection",
        json={"selected_text": "Build onboarding analytics", "instruction": "Make the problem statement sharper"},
    )
    assert revise_response.status_code == 200

    workspace_after_revision = client.get(f"/tasks/{task['id']}/workspace").json()
    assert any(file["path"].startswith("versions/") for file in workspace_after_revision["files"])

    checklist_response = client.post(f"/sessions/{session['id']}/checklist/run")
    assert checklist_response.status_code == 200
    assert "reviews/checklist_result.md" in checklist_response.json()["paths"]

    export_response = client.post(f"/sessions/{session['id']}/artifacts/export-markdown")
    assert export_response.status_code == 200
    assert export_response.json()["artifact_path"] == "artifacts/prd-draft.md"

    timeline = client.get(f"/sessions/{session['id']}/timeline").json()
    event_kinds = [event["kind"] for event in timeline]
    assert "convert_input" in event_kinds
    assert "propose_outline" in event_kinds
    assert "approve_outline" in event_kinds
    assert "revise_selection" in event_kinds
    assert "run_checklist" in event_kinds
    assert "export_markdown" in event_kinds


def test_phase2_non_prd_authoring_loop_uses_generic_doc_type_paths(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))
    client.post("/skill-packs", json={"id": "memo", "title": "Memo", "description": ""})
    client.put("/skill-packs/memo/artifacts", json={
        "path": "SKILL.md",
        "content": "---\nname: memo\ndescription: Use for memos.\n---\n\n# Memo\n",
        "summary": "Initial memo skill",
    })
    version = client.post("/skill-packs/memo/publish", json={"publish_note": "Memo v1"}).json()
    task = client.post("/tasks", json={
        "doc_type_id": "memo",
        "pack_version_id": version["id"],
        "brief": "Write a board memo",
    }).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    start_response = client.post(f"/sessions/{session['id']}/loop/start")
    assert start_response.status_code == 200
    outline = client.get(f"/tasks/{task['id']}/workspace/files", params={"path": "draft/outline.md"}).json()
    approve_response = client.post(
        f"/sessions/{session['id']}/outline/approve",
        json={"outline_markdown": outline["content"]},
    )
    assert approve_response.status_code == 200

    draft = client.get(f"/tasks/{task['id']}/draft").json()["markdown"]
    assert "# Memo Draft" in draft
    assert "# PRD Draft" not in draft

    export_response = client.post(f"/sessions/{session['id']}/artifacts/export-markdown")
    assert export_response.status_code == 200
    assert export_response.json()["artifact_path"] == "artifacts/memo-draft.md"


def test_phase2_session_statuses_are_persisted(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build onboarding analytics"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    start_response = client.post(f"/sessions/{session['id']}/loop/start")
    assert start_response.status_code == 200
    assert client.get(f"/sessions/{session['id']}").json()["status"] == "await_outline_approval"

    outline = client.get(f"/tasks/{task['id']}/workspace/files", params={"path": "draft/outline.md"}).json()
    approve_response = client.post(
        f"/sessions/{session['id']}/outline/approve",
        json={"outline_markdown": outline["content"]},
    )

    assert approve_response.status_code == 200
    assert client.get(f"/sessions/{session['id']}").json()["status"] == "draft_ready"


def test_revise_selection_before_draft_returns_400(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build onboarding analytics"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    response = client.post(
        f"/sessions/{session['id']}/revision/selection",
        json={"selected_text": "Build onboarding analytics", "instruction": "Make it sharper"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Draft does not exist. Approve the outline first."


def test_revise_selection_missing_text_returns_422(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Build onboarding analytics"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    client.post(f"/sessions/{session['id']}/loop/start")
    outline = client.get(f"/tasks/{task['id']}/workspace/files", params={"path": "draft/outline.md"}).json()
    client.post(f"/sessions/{session['id']}/outline/approve", json={"outline_markdown": outline["content"]})

    response = client.post(
        f"/sessions/{session['id']}/revision/selection",
        json={"selected_text": "Not in draft", "instruction": "Make it sharper"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Selected text not found in draft."
