from pathlib import Path

from fastapi.testclient import TestClient

from docagent_api.app import create_app


def test_create_pack_add_resource_validate_and_publish(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))

    created = client.post("/skill-packs", json={
        "id": "risk-report",
        "title": "Risk Report",
        "description": "Board risk memo pack",
    })
    assert created.status_code == 200
    assert created.json()["id"] == "risk-report"

    resource = client.post("/skill-packs/risk-report/resources/text", json={
        "group": "examples",
        "name": "example.txt",
        "content": "Strong reports begin with material risk and mitigation owner.",
    })
    assert resource.status_code == 200
    assert resource.json()["status"] == "ready"
    assert resource.json()["markdown_path"].endswith(".md")

    artifact = client.put("/skill-packs/risk-report/artifacts", json={
        "path": "SKILL.md",
        "content": "---\nname: risk-report\ndescription: Use for enterprise risk reports.\n---\n\n# Risk Report\n",
        "summary": "Human-authored initial skill",
    })
    assert artifact.status_code == 200

    validation = client.post("/skill-packs/risk-report/validate").json()
    assert validation["status"] == "passed"

    published = client.post("/skill-packs/risk-report/publish", json={"publish_note": "First version"})
    assert published.status_code == 200
    assert published.json()["version"] == "v001"


def test_pack_artifact_path_traversal_is_rejected(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))
    client.post("/skill-packs", json={"id": "memo", "title": "Memo", "description": ""})

    response = client.put("/skill-packs/memo/artifacts", json={
        "path": "../outside.md",
        "content": "# Nope\n",
        "summary": "Traversal attempt",
    })

    assert response.status_code == 400


def test_create_pack_add_text_resource_uses_conversion_report_contract(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))
    client.post("/skill-packs", json={"id": "memo", "title": "Memo", "description": ""})

    response = client.post("/skill-packs/memo/resources/text", json={
        "group": "examples",
        "name": "example.txt",
        "content": "Memo body",
    })

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["markdown_path"] == "resources/markdown/examples/example.md"
    assert body["conversion_report_path"] == "resources/reports/examples/example.conversion.json"
