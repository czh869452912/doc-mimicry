import zipfile
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient

from docagent_api.app import create_app


def _docx_bytes(text: str) -> bytes:
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>{text}</w:t></w:r></w:p>
  </w:body>
</w:document>"""
    content_types = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


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


def test_upload_skill_pack_resource_file_converts_docx(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))
    client.post("/skill-packs", json={"id": "memo", "title": "Memo", "description": ""})

    response = client.post(
        "/skill-packs/memo/resources/files",
        data={"group": "examples"},
        files={
            "file": (
                "memo.docx",
                _docx_bytes("Memo example"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ready", "warning"}
    assert body["source_path"] == "resources/original/examples/memo.docx"
    assert body["markdown_path"] == "resources/markdown/examples/memo.md"
    assert body["warnings"][0]["type"] == "docx_format_loss"


def test_skill_pack_resource_detail_exposes_markdown_and_warnings(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    client.post("/skill-packs", json={"id": "memo", "title": "Memo"})
    resource = client.post(
        "/skill-packs/memo/resources/text",
        json={"group": "examples", "name": "memo.txt", "content": "Memo pattern"},
    ).json()

    list_response = client.get("/skill-packs/memo/resources")
    detail_response = client.get(f"/skill-packs/memo/resources/{resource['id']}")

    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [resource["id"]]
    assert "warnings" in list_response.json()[0]
    assert "markdown" not in list_response.json()[0]
    assert "conversion_report" not in list_response.json()[0]
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["markdown"] == "Memo pattern\n"
    assert detail["conversion_report"]["source_path"] == "resources/original/examples/memo.txt"
    assert detail["warnings"] == []
