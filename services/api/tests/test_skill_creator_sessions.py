from pathlib import Path

from fastapi.testclient import TestClient

from docagent_api.app import create_app


def _pack_with_resource(client: TestClient) -> None:
    client.post("/skill-packs", json={"id": "memo", "title": "Memo", "description": "Memo pack"})
    client.post("/skill-packs/memo/resources/text", json={
        "group": "examples",
        "name": "memo-example.txt",
        "content": "A useful memo starts with decision context, recommendation, and risk.",
    })


def test_skill_creator_generate_writes_artifacts_and_events(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))
    _pack_with_resource(client)

    session = client.post("/skill-packs/memo/skill-creator/sessions", json={
        "message": "Generate a memo skill from the uploaded material."
    }).json()
    assert session["session_scope"] == "pack-management"

    result = client.post(f"/skill-packs/memo/skill-creator/sessions/{session['id']}/generate", json={
        "message": "Generate the initial skill pack."
    })
    assert result.status_code == 200
    assert "SKILL.md" in result.json()["paths"]

    skill = client.get("/skill-packs/memo/artifacts", params={"path": "SKILL.md"}).json()
    assert "memo" in skill["content"].lower()

    events = client.get(f"/skill-packs/memo/skill-creator/sessions/{session['id']}/events").json()
    assert any(event["event_type"] == "file/write" for event in events)


def test_skill_creator_revision_reads_manual_edit(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))
    _pack_with_resource(client)
    session = client.post("/skill-packs/memo/skill-creator/sessions", json={"message": "Start"}).json()
    client.put("/skill-packs/memo/artifacts", json={
        "path": "SKILL.md",
        "content": "---\nname: memo\ndescription: Use for executive memos.\n---\n\n# Executive Memo\n\nPreserve this line.\n",
        "summary": "Manual edit",
    })

    response = client.post(f"/skill-packs/memo/skill-creator/sessions/{session['id']}/messages", json={
        "message": "Make the checklist stricter without removing my manual line."
    })

    assert response.status_code == 200
    skill = client.get("/skill-packs/memo/artifacts", params={"path": "SKILL.md"}).json()
    assert "Preserve this line." in skill["content"]
    events = client.get(f"/skill-packs/memo/skill-creator/sessions/{session['id']}/events").json()
    event_types = [event["event_type"] for event in events]
    assert "file/read" in event_types
    assert event_types.index("file/read") < event_types.index("file/write")
