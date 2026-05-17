import zipfile
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient

from docagent_api.app import create_app
from docagent_api.imports import import_text_input


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


def test_import_text_input_writes_original_markdown_and_report(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"

    result = import_text_input(
        workspace_root=workspace,
        name="notes.txt",
        content="User research notes",
        created_at="2026-04-30T00:00:00Z",
    )

    assert result["status"] == "converted"
    assert result["source_path"] == "inputs/original/notes.txt"
    assert result["markdown_path"] == "inputs/markdown/notes.md"
    assert result["conversion_report_path"] == "inputs/reports/notes.conversion.json"
    assert result["warnings"] == []
    assert (workspace / "inputs" / "original" / "notes.txt").read_text(encoding="utf-8") == "User research notes\n"
    assert (workspace / "inputs" / "markdown" / "notes.md").read_text(encoding="utf-8") == "User research notes\n"
    assert (workspace / "inputs" / "reports" / "notes.conversion.json").exists()


def test_import_text_input_uses_unique_paths_for_duplicate_names(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"

    first = import_text_input(workspace, "notes.md", "First", "2026-04-30T00:00:00Z")
    second = import_text_input(workspace, "notes.md", "Second", "2026-04-30T00:01:00Z")

    assert first["markdown_path"] == "inputs/markdown/notes.md"
    assert second["markdown_path"] == "inputs/markdown/notes-2.md"
    assert (workspace / "inputs" / "markdown" / "notes.md").read_text(encoding="utf-8") == "First\n"
    assert (workspace / "inputs" / "markdown" / "notes-2.md").read_text(encoding="utf-8") == "Second\n"


def test_upload_docx_input_converts_to_markdown_and_records_event(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Use uploaded material"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    response = client.post(
        f"/tasks/{task['id']}/inputs/files",
        files={
            "file": (
                "source.docx",
                _docx_bytes("Uploaded Word"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "converted"
    assert body["source_path"] == "inputs/original/source.docx"
    assert body["markdown_path"] == "inputs/markdown/source.md"
    assert (Path(task["workspace_root"]) / body["markdown_path"]).read_text(encoding="utf-8") == "Uploaded Word\n"
    events = client.get(f"/sessions/{session['id']}/timeline").json()
    assert any(event["kind"] == "convert_input" for event in events)


def test_file_input_conversion_is_mirrored_to_acp_events(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Use the uploaded notes"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    response = client.post(
        f"/tasks/{task['id']}/inputs/files",
        files={"file": ("notes.txt", b"Converted material", "text/plain")},
    )

    assert response.status_code == 200
    acp_events = client.get(f"/sessions/{session['id']}/events").json()
    assert any(
        event["event_type"] == "docagent/projection"
        and event["projection"]["timeline_kind"] == "convert_input"
        and "inputs/markdown/notes.md" in event["projection"]["paths"]
        for event in acp_events
    )


def test_upload_unsupported_input_returns_report_without_markdown_attachment(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Use uploaded material"}).json()

    response = client.post(
        f"/tasks/{task['id']}/inputs/files",
        files={
            "file": (
                "deck.pptx",
                b"not a deck",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["markdown_path"] is None
    assert body["warnings"][0]["type"] == "unsupported_format"
