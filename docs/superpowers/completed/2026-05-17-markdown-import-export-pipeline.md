# Markdown Import Export Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build product import/export boundaries that accept Word and PDF while keeping Markdown as the only internal document format.

**Architecture:** Add a shared `packages/conversion` package used by API routes and CLI tools. Authoring inputs and Skill Pack resources both write originals, converted Markdown, assets, and conversion reports through the same conversion boundary. Export is a backend-owned product action that reads `draft/draft.md` and creates DOCX/PDF artifacts under the workspace `artifacts/` directory.

**Tech Stack:** Python 3, FastAPI multipart upload, built-in `zipfile`/`xml.etree.ElementTree` for minimal DOCX import/export, `pypdf` for digital PDF text import, a small built-in PDF writer for Markdown-to-PDF MVP, React/Vite/TypeScript frontend.

---

## Hard Constraints

- Markdown is the only editable/internal document format.
- DOCX and PDF may appear only as originals, export references, conversion inputs, or exported artifacts.
- Agents read converted Markdown and conversion reports, not original binary files.
- Failed conversions keep originals and write reports; they do not create message attachments with usable `markdown_path`.
- Existing text import endpoints remain compatible wrappers over the new conversion boundary.
- Each task should be committed separately.

## File Map

- Create `packages/conversion/docagent_conversion/__init__.py`: public conversion/export package API.
- Create `packages/conversion/docagent_conversion/importers.py`: safe import path allocation, text/Markdown/HTML/DOCX/PDF conversion, report writing.
- Create `packages/conversion/docagent_conversion/exporters.py`: Markdown-to-DOCX and Markdown-to-PDF artifact writers.
- Create `packages/conversion/tests/test_importers.py`: conversion package import tests.
- Create `packages/conversion/tests/test_exporters.py`: export package tests.
- Modify `packages/contracts/docagent_contracts/models.py`: add `pypdf` to the conversion engine enum.
- Modify `packages/contracts/schemas.md`: document the `pypdf` conversion engine.
- Modify `packages/contracts/tests/test_models.py`: assert `ConversionEngine.PYPDF`.
- Modify `pyproject.toml`: add `packages/conversion` to pytest pythonpath and add `pypdf`.
- Modify `services/api/Dockerfile`: add `/app/packages/conversion` to runtime `PYTHONPATH`.
- Modify `tools/import/convert_to_markdown.py`: delegate to `docagent_conversion.importers`.
- Modify `tools/import/tests/test_convert_to_markdown.py`: align CLI report expectations.
- Create `tools/export/export_docx.py` and `tools/export/export_pdf.py`: CLI wrappers.
- Modify `tools/export/README.md`: replace planned-only wording with actual commands.
- Modify `services/api/docagent_api/imports.py`: wrap shared conversion for authoring inputs.
- Modify `services/api/docagent_api/skill_packs.py`: wrap shared conversion for Skill Pack resources.
- Modify `services/api/docagent_api/request_models.py`: no model change is expected for multipart uploads because FastAPI receives file and form fields directly.
- Modify `services/api/docagent_api/response_models.py`: allow nullable `markdown_path` and include warnings/status fields.
- Modify `services/api/docagent_api/routes/tasks.py`: add multipart input upload route.
- Modify `services/api/docagent_api/routes/skill_packs.py`: add multipart resource upload route.
- Modify `services/api/docagent_api/routes/sessions.py`: add DOCX/PDF export routes.
- Modify `apps/web/src/api.ts`: add file upload and DOCX/PDF export clients.
- Modify `apps/web/src/types.ts`: support nullable `ImportedInput.markdown_path`, warnings, and export route results.
- Modify `apps/web/src/shell/acp/AcpComposer.tsx`: upload `File` objects instead of reading every attachment with `file.text()`.
- Modify `apps/web/src/shell/management/SkillPackManager.tsx`: add file upload for resources.
- Modify `apps/web/src/shell/conversation/slashCommands.ts`: add DOCX/PDF export commands.
- Update related tests under `services/api/tests`, `apps/web/src/shell/**/__tests__`, and `apps/web/tests`.
- Modify `docs/architecture/markdown-pipeline.md`, `docs/architecture/event-model.md`, and `docs/index.md`: sync implementation facts and verification commands.

## Task 1: Add Shared Conversion Package

**Files:**
- Create: `packages/conversion/docagent_conversion/__init__.py`
- Create: `packages/conversion/docagent_conversion/importers.py`
- Create: `packages/conversion/tests/test_importers.py`
- Modify: `packages/contracts/docagent_contracts/models.py`
- Modify: `packages/contracts/schemas.md`
- Modify: `packages/contracts/tests/test_models.py`
- Modify: `pyproject.toml`
- Modify: `services/api/Dockerfile`

- [ ] **Step 1: Add failing conversion package tests**

Create `packages/conversion/tests/test_importers.py`:

```python
import json
import zipfile
from pathlib import Path

from docagent_conversion import ConversionLayout, convert_resource_bytes


def _docx_bytes(text: str) -> bytes:
    from io import BytesIO

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


def _layout(root: Path) -> ConversionLayout:
    return ConversionLayout(
        root=root,
        original_dir="inputs/original",
        markdown_dir="inputs/markdown",
        assets_dir="inputs/assets",
        reports_dir="inputs/reports",
    )


def test_converts_markdown_bytes_to_workspace_layout(tmp_path: Path) -> None:
    result = convert_resource_bytes(
        _layout(tmp_path),
        original_filename="brief.md",
        content=b"# Brief\n",
        mime_type="text/markdown",
        created_at="2026-05-17T00:00:00Z",
    )

    assert result["status"] == "converted"
    assert result["source_path"] == "inputs/original/brief.md"
    assert result["markdown_path"] == "inputs/markdown/brief.md"
    assert result["conversion_report_path"] == "inputs/reports/brief.conversion.json"
    assert (tmp_path / result["markdown_path"]).read_text(encoding="utf-8") == "# Brief\n"


def test_converts_html_to_markdown_text(tmp_path: Path) -> None:
    result = convert_resource_bytes(
        _layout(tmp_path),
        original_filename="page.html",
        content=b"<h1>Title</h1><p>Body text</p>",
        mime_type="text/html",
        created_at="2026-05-17T00:00:00Z",
    )

    assert result["status"] == "converted"
    markdown = (tmp_path / result["markdown_path"]).read_text(encoding="utf-8")
    assert "Title" in markdown
    assert "Body text" in markdown


def test_converts_docx_to_markdown_without_keeping_docx_internal(tmp_path: Path) -> None:
    result = convert_resource_bytes(
        _layout(tmp_path),
        original_filename="source.docx",
        content=_docx_bytes("Docx body"),
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        created_at="2026-05-17T00:00:00Z",
    )

    assert result["status"] == "converted"
    assert result["source_path"] == "inputs/original/source.docx"
    assert result["markdown_path"] == "inputs/markdown/source.md"
    assert (tmp_path / result["markdown_path"]).read_text(encoding="utf-8") == "Docx body\n"


def test_converts_digital_pdf_to_markdown(tmp_path: Path) -> None:
    from docagent_conversion.exporters import _simple_pdf_bytes

    result = convert_resource_bytes(
        _layout(tmp_path),
        original_filename="source.pdf",
        content=_simple_pdf_bytes(["PDF body"]),
        mime_type="application/pdf",
        created_at="2026-05-17T00:00:00Z",
    )

    assert result["status"] == "converted"
    assert result["source_path"] == "inputs/original/source.pdf"
    assert result["markdown_path"] == "inputs/markdown/source.md"
    assert "PDF body" in (tmp_path / result["markdown_path"]).read_text(encoding="utf-8")


def test_unsupported_binary_keeps_original_and_failed_report(tmp_path: Path) -> None:
    result = convert_resource_bytes(
        _layout(tmp_path),
        original_filename="deck.pptx",
        content=b"not a supported deck",
        mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        created_at="2026-05-17T00:00:00Z",
    )

    assert result["status"] == "failed"
    assert result["markdown_path"] is None
    assert (tmp_path / "inputs/original/deck.pptx").read_bytes() == b"not a supported deck"
    report = json.loads((tmp_path / result["conversion_report_path"]).read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert report["warnings"][0]["type"] == "unsupported_format"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest packages/contracts/tests packages/conversion/tests/test_importers.py -q
```

Expected: FAIL because `docagent_conversion` does not exist.

- [ ] **Step 3: Add conversion package to pytest path and dependency**

In `packages/contracts/docagent_contracts/models.py`, add the PDF text
extractor engine:

```python
class ConversionEngine(str, Enum):
    DOCLING = "docling"
    MARKITDOWN = "markitdown"
    PANDOC = "pandoc"
    MINERU = "mineru"
    MARKER = "marker"
    PYPDF = "pypdf"
    MANUAL = "manual"
    UNKNOWN = "unknown"
```

In `packages/contracts/schemas.md`, update the `ConversionReport.engine`
line:

```markdown
engine: docling | markitdown | pandoc | mineru | marker | pypdf | manual | unknown
```

In `packages/contracts/tests/test_models.py`, add an assertion beside the
existing conversion report assertions:

```python
assert ConversionEngine.PYPDF.value == "pypdf"
```

Modify `pyproject.toml`:

```toml
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn>=0.30.0",
  "sqlalchemy>=2.0",
  "psycopg2-binary>=2.9",
  "alembic>=1.13",
  "celery[redis]>=5.3",
  "redis>=5.0",
  "PyYAML>=6.0",
  "pypdf>=5.0",
]

[tool.pytest.ini_options]
pythonpath = [
  "packages/contracts",
  "packages/conversion",
  "packages/workspace",
  "packages/timeline",
  "tools/import",
  "services/api",
  "agent/runtime-adapters/mock",
  "agent/runtime-adapters/openhands"
]
```

Modify `services/api/Dockerfile` so the running API container can import the
new package. Replace the existing `PYTHONPATH=` line with:

```dockerfile
    PYTHONPATH=/app/services/api:/app/packages/contracts:/app/packages/conversion:/app/packages/workspace:/app/packages/timeline:/app/tools/import:/app/agent/runtime-adapters/mock:/app/agent/runtime-adapters/openhands
```

- [ ] **Step 4: Implement shared importer**

Create `packages/conversion/docagent_conversion/__init__.py`:

```python
from .importers import ConversionLayout, convert_resource_bytes

__all__ = ["ConversionLayout", "convert_resource_bytes"]
```

Create `packages/conversion/docagent_conversion/exporters.py` with the
minimal PDF helper used by the import test. Task 6 will add the public export
functions to this file:

```python
from __future__ import annotations

import textwrap


def _simple_pdf_bytes(lines: list[str]) -> bytes:
    rendered = []
    y = 760
    for line in lines:
        for wrapped in textwrap.wrap(line, width=88) or [""]:
            safe = wrapped.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            rendered.append(f"BT /F1 11 Tf 50 {y} Td ({safe}) Tj ET")
            y -= 16
            if y < 60:
                y = 760
    stream = "\n".join(rendered).encode("latin-1", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    chunks = [b"%PDF-1.4\n"]
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(sum(len(chunk) for chunk in chunks))
        chunks.append(f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n")
    xref_offset = sum(len(chunk) for chunk in chunks)
    chunks.append(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        chunks.append(f"{offset:010d} 00000 n \n".encode("ascii"))
    chunks.append(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return b"".join(chunks)
```

Create `packages/conversion/docagent_conversion/importers.py` with:

```python
from __future__ import annotations

import html.parser
import json
import re
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


@dataclass(frozen=True)
class ConversionLayout:
    root: Path
    original_dir: str
    markdown_dir: str
    assets_dir: str
    reports_dir: str


def convert_resource_bytes(
    layout: ConversionLayout,
    original_filename: str,
    content: bytes,
    mime_type: str,
    created_at: str,
) -> dict[str, Any]:
    stem = _unique_stem(layout, _safe_stem(original_filename), Path(original_filename).suffix.lower())
    suffix = Path(original_filename).suffix.lower()
    source_path = layout.root / layout.original_dir / f"{stem}{suffix or '.bin'}"
    markdown_path = layout.root / layout.markdown_dir / f"{stem}.md"
    report_path = layout.root / layout.reports_dir / f"{stem}.conversion.json"
    asset_dir = layout.root / layout.assets_dir / stem
    for path in [source_path.parent, markdown_path.parent, report_path.parent]:
        path.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(content)

    warnings: list[dict[str, str | None]] = []
    markdown: str | None = None
    engine = "manual"
    features = {"tables": 0, "images": 0, "formulas": 0, "footnotes": 0, "pages": None}

    try:
        if suffix in {".md", ".markdown"}:
            markdown = _decode_text(content)
        elif suffix == ".txt":
            markdown = _decode_text(content)
        elif suffix in {".html", ".htm"}:
            markdown = _html_to_markdown(_decode_text(content))
            warnings.append({"type": "html_format_loss", "message": "HTML styling was reduced to Markdown text.", "location": None})
        elif suffix == ".docx":
            markdown = _docx_to_markdown(content)
            warnings.append({"type": "docx_format_loss", "message": "DOCX layout and styling were reduced to Markdown text.", "location": None})
        elif suffix == ".pdf":
            engine = "pypdf"
            markdown, page_count = _pdf_to_markdown(content)
            features["pages"] = page_count
            warnings.append({"type": "pdf_format_loss", "message": "PDF layout was reduced to extracted text.", "location": None})
        else:
            warnings.append({"type": "unsupported_format", "message": f"Unsupported import format: {suffix or 'no extension'}.", "location": None})
    except Exception as exc:
        warnings.append({"type": "conversion_failed", "message": str(exc), "location": None})

    if markdown is not None and markdown.strip():
        asset_dir.mkdir(parents=True, exist_ok=True)
        text = markdown if markdown.endswith("\n") else f"{markdown}\n"
        markdown_path.write_text(text, encoding="utf-8")
        report_status = "succeeded_with_warnings" if warnings else "succeeded"
        result_status = "converted"
        result_markdown_path = markdown_path.relative_to(layout.root).as_posix()
    else:
        report_status = "failed"
        result_status = "failed"
        result_markdown_path = None

    report = {
        "source_path": source_path.relative_to(layout.root).as_posix(),
        "markdown_path": result_markdown_path,
        "asset_dir": asset_dir.relative_to(layout.root).as_posix() if result_markdown_path else None,
        "engine": engine if result_markdown_path else "unknown",
        "status": report_status,
        "warnings": warnings,
        "features_detected": features,
        "created_at": created_at,
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "id": f"input-{stem}",
        "status": result_status,
        "source_path": report["source_path"],
        "markdown_path": result_markdown_path,
        "asset_dir": report["asset_dir"],
        "conversion_report_path": report_path.relative_to(layout.root).as_posix(),
        "mime_type": mime_type,
        "original_filename": original_filename,
        "warnings": warnings,
        "created_at": created_at,
    }
```

Also include helper functions `_safe_stem`, `_unique_stem`, `_decode_text`, `_html_to_markdown`, `_docx_to_markdown`, and `_pdf_to_markdown` in the same file:

```python
def _safe_stem(name: str) -> str:
    raw_stem = Path(name).stem or "input"
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", raw_stem).strip("-").lower()
    return stem or "input"


def _unique_stem(layout: ConversionLayout, base_stem: str, source_suffix: str) -> str:
    stem = base_stem
    suffix = 2
    source_suffix = source_suffix or ".bin"
    while (
        (layout.root / layout.original_dir / f"{stem}{source_suffix}").exists()
        or (layout.root / layout.markdown_dir / f"{stem}.md").exists()
        or (layout.root / layout.reports_dir / f"{stem}.conversion.json").exists()
    ):
        stem = f"{base_stem}-{suffix}"
        suffix += 1
    return stem


def _decode_text(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("latin-1")


class _TextExtractor(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"h1", "h2", "h3", "p", "li", "br", "tr"}:
            self.parts.append("\n")
        if tag == "li":
            self.parts.append("- ")

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)
            self.parts.append(" ")


def _html_to_markdown(text: str) -> str:
    # MVP keeps HTML text readable but does not preserve heading levels or rich layout.
    parser = _TextExtractor()
    parser.feed(text)
    lines = [" ".join(line.split()) for line in "".join(parser.parts).splitlines()]
    return "\n".join(line for line in lines if line)


def _docx_to_markdown(content: bytes) -> str:
    with zipfile.ZipFile(BytesIO(content)) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        pieces = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
        text = "".join(pieces).strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def _pdf_to_markdown(content: bytes) -> tuple[str, int]:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(content))
    pages: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append(f"## Page {index}\n\n{text}")
    return "\n\n".join(pages), len(reader.pages)
```

- [ ] **Step 5: Run conversion tests**

Run:

```powershell
python -m pytest packages/conversion/tests/test_importers.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 1**

```powershell
git add pyproject.toml services/api/Dockerfile packages/contracts/docagent_contracts/models.py packages/contracts/schemas.md packages/contracts/tests/test_models.py packages/conversion/docagent_conversion packages/conversion/tests/test_importers.py
git commit -m "feat: add shared conversion importer"
```

## Task 2: Port Existing Text Imports To Shared Conversion

**Files:**
- Modify: `services/api/docagent_api/imports.py`
- Modify: `services/api/docagent_api/skill_packs.py`
- Modify: `services/api/docagent_api/response_models.py`
- Modify: `services/api/tests/test_imports.py`
- Modify: `services/api/tests/test_skill_packs.py`
- Modify: `services/api/tests/test_skill_pack_routes.py`

- [ ] **Step 1: Write failing compatibility tests**

In `services/api/tests/test_imports.py`, update the first test to expect `.conversion.json` and warnings:

```python
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
    assert (workspace / "inputs/original/notes.txt").read_text(encoding="utf-8") == "User research notes\n"
    assert (workspace / "inputs/markdown/notes.md").read_text(encoding="utf-8") == "User research notes\n"
    assert (workspace / "inputs/reports/notes.conversion.json").exists()
```

Add a Skill Pack route assertion in `services/api/tests/test_skill_pack_routes.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest services/api/tests/test_imports.py services/api/tests/test_skill_pack_routes.py -q
```

Expected: FAIL because current wrappers still write `*.json` reports and do not include `warnings`.

- [ ] **Step 3: Update authoring import wrapper**

Replace `services/api/docagent_api/imports.py` implementation with a wrapper around `docagent_conversion`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from docagent_conversion import ConversionLayout, convert_resource_bytes


def import_text_input(
    workspace_root: Path,
    name: str,
    content: str,
    created_at: str,
) -> dict[str, Any]:
    layout = ConversionLayout(
        root=workspace_root,
        original_dir="inputs/original",
        markdown_dir="inputs/markdown",
        assets_dir="inputs/assets",
        reports_dir="inputs/reports",
    )
    text = content if content.endswith("\n") else f"{content}\n"
    return convert_resource_bytes(
        layout,
        original_filename=name,
        content=text.encode("utf-8"),
        mime_type="text/plain",
        created_at=created_at,
    )
```

- [ ] **Step 4: Update Skill Pack text resource wrapper**

In `services/api/docagent_api/skill_packs.py`, replace `add_text_resource` internals with shared conversion and status mapping:

```python
def add_text_resource(
    state: DocAgentState,
    pack_id: str,
    group: str,
    name: str,
    content: str,
) -> dict[str, Any]:
    if group not in PACK_GROUPS:
        raise ValueError("Invalid resource group")
    root = draft_root(state, pack_id)
    layout = ConversionLayout(
        root=root,
        original_dir=f"resources/original/{group}",
        markdown_dir=f"resources/markdown/{group}",
        assets_dir=f"resources/assets/{group}",
        reports_dir=f"resources/reports/{group}",
    )
    text = content if content.endswith("\n") else f"{content}\n"
    converted = convert_resource_bytes(
        layout,
        original_filename=name,
        content=text.encode("utf-8"),
        mime_type="text/plain",
        created_at=utc_now(),
    )
    status = "ready" if converted["status"] == "converted" and not converted["warnings"] else "warning"
    if converted["status"] != "converted":
        status = "failed"
    return {
        "id": f"resource-{uuid4().hex[:12]}",
        "pack_id": pack_id,
        "group": group,
        "original_filename": name,
        "source_path": converted["source_path"],
        "markdown_path": converted["markdown_path"],
        "conversion_report_path": converted["conversion_report_path"],
        "status": status,
        "summary": "",
    }
```

Also add imports:

```python
from docagent_conversion import ConversionLayout, convert_resource_bytes
```

- [ ] **Step 5: Update response model**

In `services/api/docagent_api/response_models.py`, change `ImportedInputResponse`:

```python
class ImportedInputResponse(BaseModel):
    id: str
    status: str
    source_path: str
    markdown_path: str | None = None
    conversion_report_path: str
    original_filename: str
    created_at: str
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    event: dict | None = None
```

- [ ] **Step 6: Run focused tests**

Run:

```powershell
python -m pytest services/api/tests/test_imports.py services/api/tests/test_skill_pack_routes.py services/api/tests/test_skill_packs.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 2**

```powershell
git add services/api/docagent_api/imports.py services/api/docagent_api/skill_packs.py services/api/docagent_api/response_models.py services/api/tests/test_imports.py services/api/tests/test_skill_pack_routes.py services/api/tests/test_skill_packs.py
git commit -m "refactor: share conversion for text resources"
```

## Task 3: Add Multipart Upload Routes

**Files:**
- Modify: `services/api/docagent_api/routes/tasks.py`
- Modify: `services/api/docagent_api/routes/skill_packs.py`
- Modify: `services/api/tests/test_imports.py`
- Modify: `services/api/tests/test_skill_pack_routes.py`

- [ ] **Step 1: Add failing authoring upload route tests**

Append to `services/api/tests/test_imports.py`:

```python
import zipfile
from io import BytesIO

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


def test_upload_docx_input_converts_to_markdown_and_records_event(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Use uploaded material"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    response = client.post(
        f"/tasks/{task['id']}/inputs/files",
        files={"file": ("source.docx", _docx_bytes("Uploaded Word"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "converted"
    assert body["source_path"] == "inputs/original/source.docx"
    assert body["markdown_path"] == "inputs/markdown/source.md"
    assert (Path(task["workspace_root"]) / body["markdown_path"]).read_text(encoding="utf-8") == "Uploaded Word\n"
    events = client.get(f"/sessions/{session['id']}/timeline").json()
    assert any(event["kind"] == "convert_input" for event in events)


def test_upload_unsupported_input_returns_report_without_markdown_attachment(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Use uploaded material"}).json()

    response = client.post(
        f"/tasks/{task['id']}/inputs/files",
        files={"file": ("deck.pptx", b"not a deck", "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["markdown_path"] is None
    assert body["warnings"][0]["type"] == "unsupported_format"
```

- [ ] **Step 2: Add failing Skill Pack upload route test**

Append to `services/api/tests/test_skill_pack_routes.py`:

```python
import zipfile
from io import BytesIO


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


def test_upload_skill_pack_resource_file_converts_docx(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path(".")))
    client.post("/skill-packs", json={"id": "memo", "title": "Memo", "description": ""})

    response = client.post(
        "/skill-packs/memo/resources/files",
        data={"group": "examples"},
        files={"file": ("memo.docx", _docx_bytes("Memo example"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ready", "warning"}
    assert body["source_path"] == "resources/original/examples/memo.docx"
    assert body["markdown_path"] == "resources/markdown/examples/memo.md"
```

- [ ] **Step 3: Run route tests to verify failure**

Run:

```powershell
python -m pytest services/api/tests/test_imports.py services/api/tests/test_skill_pack_routes.py -q
```

Expected: FAIL with 404 for the new routes.

- [ ] **Step 4: Add FastAPI multipart imports and routes**

In `services/api/docagent_api/routes/tasks.py`, add imports:

```python
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from docagent_conversion import ConversionLayout, convert_resource_bytes
```

Add route after `add_text_input`:

```python
    @router.post("/tasks/{task_id}/inputs/files", response_model=ImportedInputResponse)
    async def add_file_input(task_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
        task = require_task(state, task_id)
        content = await file.read()
        result = convert_resource_bytes(
            ConversionLayout(
                root=Path(task["workspace_root"]),
                original_dir="inputs/original",
                markdown_dir="inputs/markdown",
                assets_dir="inputs/assets",
                reports_dir="inputs/reports",
            ),
            original_filename=file.filename or "upload.bin",
            content=content,
            mime_type=file.content_type or "application/octet-stream",
            created_at=utc_now(),
        )
        sessions = state.list_sessions_by_task(task_id)
        if sessions:
            latest = max(sessions, key=lambda s: s.get("updated_at", ""))
            event = manual_event(
                task_id,
                latest["id"],
                f"convert-input-{result['id']}",
                TimelineActor.SYSTEM,
                SemanticEventKind.CONVERT_INPUT,
                "Convert input to Markdown",
                [path for path in [result.get("markdown_path"), result["conversion_report_path"]] if path],
            )
            state.append_timeline_event(latest["id"], asdict(event))
            result["event"] = asdict(event)
        return result
```

In `services/api/docagent_api/routes/skill_packs.py`, add imports:

```python
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
```

Add route after `add_pack_text_resource`:

```python
    @router.post("/skill-packs/{pack_id}/resources/files", response_model=SkillPackResourceResponse)
    async def add_pack_file_resource(
        pack_id: str,
        group: str = Form(...),
        file: UploadFile = File(...),
    ) -> dict[str, Any]:
        _require_pack(state, pack_id)
        if group not in PACK_GROUPS:
            raise HTTPException(status_code=400, detail="Invalid resource group")
        content = await file.read()
        resource = add_file_resource(
            state,
            pack_id,
            group,
            file.filename or "upload.bin",
            content,
            file.content_type or "application/octet-stream",
        )
        state.save_skill_pack_resource(resource)
        return resource
```

Add `add_file_resource` to `services/api/docagent_api/skill_packs.py` next to `add_text_resource`, using the same status mapping but passing bytes and MIME type.

- [ ] **Step 5: Ensure multipart dependency is declared**

Add to `pyproject.toml` dependencies:

```toml
"python-multipart>=0.0.9",
```

- [ ] **Step 6: Run route tests**

Run:

```powershell
python -m pytest services/api/tests/test_imports.py services/api/tests/test_skill_pack_routes.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 3**

```powershell
git add pyproject.toml services/api/docagent_api/routes/tasks.py services/api/docagent_api/routes/skill_packs.py services/api/docagent_api/skill_packs.py services/api/tests/test_imports.py services/api/tests/test_skill_pack_routes.py
git commit -m "feat: add file upload conversion routes"
```

## Task 4: Update Frontend Upload Paths

**Files:**
- Modify: `apps/web/src/api.ts`
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/shell/acp/AcpComposer.tsx`
- Modify: `apps/web/src/shell/acp/__tests__/AcpComposer.test.tsx`
- Modify: `apps/web/src/shell/acp/__tests__/AcpInteractionSurface.test.tsx`
- Modify: `apps/web/src/shell/__tests__/AppShell.test.tsx`

- [ ] **Step 1: Update failing frontend attachment tests**

In `apps/web/src/shell/acp/__tests__/AcpComposer.test.tsx`, change import assertions from `api.importTextInput` to `api.importFileInput`:

```ts
expect(api.importFileInput).toHaveBeenCalledWith("task-1", expect.any(File));
```

Add a failed conversion test:

```ts
it("does not send failed binary conversions as message attachments", async () => {
  const user = userEvent.setup();
  vi.mocked(api.importFileInput).mockResolvedValue({
    id: "input-deck",
    status: "failed",
    source_path: "inputs/original/deck.pptx",
    markdown_path: null,
    conversion_report_path: "inputs/reports/deck.conversion.json",
    original_filename: "deck.pptx",
    created_at: "2026-05-17T00:00:00Z",
    warnings: [{ type: "unsupported_format", message: "Unsupported import format: .pptx.", location: null }],
  });

  render(<AcpComposer disabled={false} taskId="task-1" onSend={vi.fn()} />);
  await user.upload(
    document.querySelector('input[type="file"]') as HTMLInputElement,
    new File(["binary"], "deck.pptx", { type: "application/vnd.openxmlformats-officedocument.presentationml.presentation" }),
  );
  await user.type(screen.getByLabelText("Message"), "Use this");
  await user.click(screen.getByLabelText("Send message"));

  expect(screen.getByText(/unsupported_format/i)).toBeTruthy();
});
```

- [ ] **Step 2: Run frontend tests to verify failure**

Run:

```powershell
cd apps/web
npm run test:unit -- --run src/shell/acp/__tests__/AcpComposer.test.tsx src/shell/acp/__tests__/AcpInteractionSurface.test.tsx src/shell/__tests__/AppShell.test.tsx
```

Expected: FAIL because `api.importFileInput` does not exist.

- [ ] **Step 3: Add file upload API client**

In `apps/web/src/api.ts`, add:

```ts
async function upload<T>(path: string, formData: FormData): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    let detail = "";
    try {
      const body = (await response.json()) as { detail?: unknown };
      detail = typeof body.detail === "string" ? `: ${body.detail}` : "";
    } catch {
      detail = "";
    }
    throw new Error(`${response.status} ${response.statusText}${detail}`);
  }
  return response.json() as Promise<T>;
}
```

Add API method:

```ts
importFileInput: (taskId: string, file: File) => {
  const formData = new FormData();
  formData.append("file", file);
  return upload<ImportedInput>(`/tasks/${taskId}/inputs/files`, formData);
},
```

In `apps/web/src/types.ts`, change:

```ts
export interface ImportedInput {
  id: string;
  status: string;
  source_path: string;
  markdown_path?: string | null;
  conversion_report_path: string;
  original_filename: string;
  created_at: string;
  warnings?: Array<{ type: string; message: string; location?: string | null }>;
  event?: TimelineEvent;
}
```

- [ ] **Step 4: Update composer to upload files directly**

In `apps/web/src/shell/acp/AcpComposer.tsx`, change pending attachments to store only `File`:

```ts
interface PendingAttachment {
  file: File;
  id: string;
  name: string;
}
```

Update `addLocalAttachments`:

```ts
function addLocalAttachments(event: ChangeEvent<HTMLInputElement>) {
  const files = Array.from(event.target.files ?? []);
  const nextAttachments = files.map((file) => ({
    file,
    id: `${file.name}-${file.size}-${file.lastModified}`,
    name: file.name,
  }));
  setAttachments((current) => [...current, ...nextAttachments]);
  event.target.value = "";
}
```

Update `importAttachments`:

```ts
async function importAttachments(): Promise<MessageAttachment[]> {
  if (attachments.length === 0) return [];
  if (!taskId) {
    setAttachmentError("Create a workspace before attaching files.");
    return [];
  }
  const imported = await Promise.all(
    attachments.map((attachment) => api.importFileInput(taskId, attachment.file)),
  );
  const failed = imported.filter((item) => !item.markdown_path);
  if (failed.length > 0) {
    const messages = failed.flatMap((item) => item.warnings?.map((warning) => warning.type) ?? [item.status]);
    setAttachmentError(`Some files were not converted: ${messages.join(", ")}`);
  }
  return imported
    .filter((item) => item.markdown_path)
    .map((item) => ({
      name: item.original_filename,
      markdown_path: item.markdown_path as string,
      source_path: item.source_path,
      conversion_report_path: item.conversion_report_path,
    }));
}
```

- [ ] **Step 5: Run frontend focused tests**

Run:

```powershell
cd apps/web
npm run test:unit -- --run src/shell/acp/__tests__/AcpComposer.test.tsx src/shell/acp/__tests__/AcpInteractionSurface.test.tsx src/shell/__tests__/AppShell.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Run browser regression for attachment flow**

Run:

```powershell
cd apps/web
npm run test -- --grep "ACP composer imports text attachments before sending"
```

Expected: PASS. The existing test name can stay as-is for this task because
Markdown upload still uses the file-upload path and should render the same
attached workspace input message.

- [ ] **Step 7: Commit Task 4**

```powershell
git add apps/web/src/api.ts apps/web/src/types.ts apps/web/src/shell/acp/AcpComposer.tsx apps/web/src/shell/acp/__tests__/AcpComposer.test.tsx apps/web/src/shell/acp/__tests__/AcpInteractionSurface.test.tsx apps/web/src/shell/__tests__/AppShell.test.tsx
git commit -m "feat: upload attachments through conversion boundary"
```

## Task 5: Add Skill Pack File Upload UI

**Files:**
- Modify: `apps/web/src/api.ts`
- Modify: `apps/web/src/shell/management/SkillPackManager.tsx`
- Modify: `apps/web/src/shell/management/__tests__/SkillPackManager.test.tsx`
- Modify: `apps/web/src/shell/__tests__/AppShell.test.tsx`

- [ ] **Step 1: Add failing management upload test**

In `SkillPackManager.test.tsx`, add:

```ts
it("uploads a Word material file into a resource group", async () => {
  const user = userEvent.setup();
  vi.mocked(api.listSkillPacks).mockResolvedValue([
    { id: "memo", title: "Memo", description: "", draft_status: "draft", latest_version_id: null },
  ]);
  vi.mocked(api.addSkillPackFileResource).mockResolvedValue({
    id: "resource-1",
    pack_id: "memo",
    group: "examples",
    original_filename: "memo.docx",
    source_path: "resources/original/examples/memo.docx",
    markdown_path: "resources/markdown/examples/memo.md",
    conversion_report_path: "resources/reports/examples/memo.conversion.json",
    status: "warning",
    summary: "",
  });

  render(<SkillPackManager />, { wrapper: queryWrapper() });
  await screen.findByText("Memo");
  await user.upload(
    screen.getByLabelText(/upload material file/i),
    new File(["docx"], "memo.docx", { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" }),
  );

  await waitFor(() => expect(api.addSkillPackFileResource).toHaveBeenCalledWith("memo", "examples", expect.any(File)));
});
```

- [ ] **Step 2: Run management test to verify failure**

Run:

```powershell
cd apps/web
npm run test:unit -- --run src/shell/management/__tests__/SkillPackManager.test.tsx
```

Expected: FAIL because `addSkillPackFileResource` and file input do not exist.

- [ ] **Step 3: Add Skill Pack file upload API**

In `apps/web/src/api.ts`, add:

```ts
addSkillPackFileResource: (packId: string, group: SkillPackResource["group"], file: File) => {
  const formData = new FormData();
  formData.append("group", group);
  formData.append("file", file);
  return upload<SkillPackResource>(`/skill-packs/${packId}/resources/files`, formData);
},
```

- [ ] **Step 4: Add file input to management panel**

In `SkillPackManager.tsx`, add a file input inside the Materials panel:

```tsx
<Label htmlFor="resource-file">Upload material file</Label>
<Input
  aria-label="Upload material file"
  id="resource-file"
  type="file"
  onChange={(event) => {
    const file = event.target.files?.[0];
    if (file) addFileResource.mutate({ group: resourceGroup, file });
    event.target.value = "";
  }}
/>
```

In `apps/web/src/shell/state/useSkillPacks.ts`, add a hook matching the text
resource mutation pattern:

```ts
export function useAddSkillPackFileResource(packId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ group, file }: { group: SkillPackResource["group"]; file: File }) => {
      if (!packId) throw new Error("Pack id is required");
      return api.addSkillPackFileResource(packId, group, file);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["skillPacks"] }),
  });
}
```

In `SkillPackManager.tsx`, create `addFileResource` with the hook:

```ts
const addFileResource = useAddSkillPackFileResource(packId);
```

- [ ] **Step 5: Run management tests**

Run:

```powershell
cd apps/web
npm run test:unit -- --run src/shell/management/__tests__/SkillPackManager.test.tsx src/shell/__tests__/AppShell.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit Task 5**

```powershell
git add apps/web/src/api.ts apps/web/src/shell/state/useSkillPacks.ts apps/web/src/shell/management/SkillPackManager.tsx apps/web/src/shell/management/__tests__/SkillPackManager.test.tsx apps/web/src/shell/__tests__/AppShell.test.tsx
git commit -m "feat: upload skill pack resource files"
```

## Task 6: Add DOCX And PDF Export Tools

**Files:**
- Modify: `packages/conversion/docagent_conversion/exporters.py`
- Create: `packages/conversion/tests/test_exporters.py`
- Create: `tools/export/export_docx.py`
- Create: `tools/export/export_pdf.py`
- Modify: `tools/export/README.md`

- [ ] **Step 1: Add failing exporter tests**

Create `packages/conversion/tests/test_exporters.py`:

```python
import zipfile
from pathlib import Path

from docagent_conversion.exporters import export_markdown_to_docx, export_markdown_to_pdf


def test_export_markdown_to_docx_creates_word_document(tmp_path: Path) -> None:
    source = tmp_path / "draft.md"
    output = tmp_path / "draft.docx"
    source.write_text("# Title\n\nBody text\n", encoding="utf-8")

    result = export_markdown_to_docx(source, output)

    assert result["status"] == "created"
    assert output.is_file()
    with zipfile.ZipFile(output) as archive:
        assert "word/document.xml" in archive.namelist()
        assert "Title" in archive.read("word/document.xml").decode("utf-8")


def test_export_markdown_to_pdf_creates_pdf_file(tmp_path: Path) -> None:
    source = tmp_path / "draft.md"
    output = tmp_path / "draft.pdf"
    source.write_text("# Title\n\nBody text\n", encoding="utf-8")

    result = export_markdown_to_pdf(source, output)

    assert result["status"] == "created"
    assert output.read_bytes().startswith(b"%PDF-")
```

- [ ] **Step 2: Run exporter tests to verify failure**

Run:

```powershell
python -m pytest packages/conversion/tests/test_exporters.py -q
```

Expected: FAIL because exporters do not exist.

- [ ] **Step 3: Implement exporters**

Extend `packages/conversion/docagent_conversion/exporters.py` with:

```python
from __future__ import annotations

import html
import zipfile
from pathlib import Path
from typing import Any


def export_markdown_to_docx(source_markdown: Path, output_path: Path) -> dict[str, Any]:
    text = source_markdown.read_text(encoding="utf-8")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document_xml = _document_xml(_markdown_lines_to_text(text))
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types_xml())
        archive.writestr("_rels/.rels", _rels_xml())
        archive.writestr("word/document.xml", document_xml)
    return {"status": "created", "kind": "docx", "path": str(output_path)}


def export_markdown_to_pdf(source_markdown: Path, output_path: Path) -> dict[str, Any]:
    text = source_markdown.read_text(encoding="utf-8")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(_simple_pdf_bytes(_markdown_lines_to_text(text)))
    return {"status": "created", "kind": "pdf", "path": str(output_path)}
```

Add helper functions in the same file:

```python
def _markdown_lines_to_text(markdown: str) -> list[str]:
    lines: list[str] = []
    for raw in markdown.splitlines():
        line = raw.strip()
        if line.startswith("#"):
            line = line.lstrip("#").strip()
        if line:
            lines.append(line)
    return lines or [""]


def _document_xml(lines: list[str]) -> str:
    paragraphs = "".join(
        f"<w:p><w:r><w:t>{html.escape(line)}</w:t></w:r></w:p>"
        for line in lines
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{paragraphs}</w:body></w:document>"
    )


def _content_types_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )


def _rels_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )
```

Keep the `_simple_pdf_bytes` helper added in Task 1 in this file; the new
`export_markdown_to_pdf` function calls it directly.


Update `packages/conversion/docagent_conversion/__init__.py`:

```python
from .exporters import export_markdown_to_docx, export_markdown_to_pdf
from .importers import ConversionLayout, convert_resource_bytes

__all__ = [
    "ConversionLayout",
    "convert_resource_bytes",
    "export_markdown_to_docx",
    "export_markdown_to_pdf",
]
```

- [ ] **Step 4: Add CLI wrappers**

Create `tools/export/export_docx.py`:

```python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "conversion"))

from docagent_conversion import export_markdown_to_docx


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = export_markdown_to_docx(Path(args.source), Path(args.output))
    print(result["path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Create `tools/export/export_pdf.py`:

```python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "conversion"))

from docagent_conversion import export_markdown_to_pdf


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = export_markdown_to_pdf(Path(args.source), Path(args.output))
    print(result["path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Update export README**

Replace `tools/export/README.md` with:

````markdown
# Export Tools

Fixed export tools convert internal Markdown drafts into external artifacts.

```powershell
python tools/export/export_docx.py --source path/to/workspace/draft/draft.md --output path/to/workspace/artifacts/draft.docx
python tools/export/export_pdf.py --source path/to/workspace/draft/draft.md --output path/to/workspace/artifacts/draft.pdf
```

These tools are boundary converters. They do not make DOCX or PDF editable
workspace formats.
````

- [ ] **Step 6: Run exporter tests and CLI smoke**

Run:

```powershell
python -m pytest packages/conversion/tests/test_exporters.py -q
```

Expected: PASS.

Run:

```powershell
$tmp = New-Item -ItemType Directory -Force .local/export-smoke
Set-Content -Path .local/export-smoke/draft.md -Value "# Title`n`nBody" -Encoding UTF8
python tools/export/export_docx.py --source .local/export-smoke/draft.md --output .local/export-smoke/draft.docx
python tools/export/export_pdf.py --source .local/export-smoke/draft.md --output .local/export-smoke/draft.pdf
```

Expected: both commands print output paths and create files.

- [ ] **Step 7: Commit Task 6**

```powershell
git add packages/conversion/docagent_conversion/__init__.py packages/conversion/docagent_conversion/exporters.py packages/conversion/tests/test_exporters.py tools/export/export_docx.py tools/export/export_pdf.py tools/export/README.md
git commit -m "feat: add markdown docx pdf exporters"
```

## Task 7: Add Backend DOCX/PDF Export Routes

**Files:**
- Modify: `services/api/docagent_api/routes/sessions.py`
- Modify: `services/api/tests/test_phase3_api.py`
- Modify: `tools/runtime/openhands_smoke.py`

- [ ] **Step 1: Add failing export route tests**

Append to `services/api/tests/test_phase3_api.py`:

```python
def test_export_docx_route_creates_artifact_without_runtime_prompt(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    client.put(f"/tasks/{task['id']}/draft", json={"markdown": "# Draft\n\nBody\n"})

    response = client.post(f"/sessions/{session['id']}/artifacts/export-docx")

    assert response.status_code == 200
    assert response.json()["artifact_path"].endswith(".docx")
    assert (Path(task["workspace_root"]) / response.json()["artifact_path"]).is_file()
    timeline = client.get(f"/sessions/{session['id']}/timeline").json()
    assert any(event["kind"] == "export_docx" for event in timeline)


def test_export_pdf_route_creates_artifact_without_runtime_prompt(tmp_path: Path) -> None:
    client = TestClient(create_app(state_root=tmp_path / "state", repo_root=Path("."), runtime_name="mock"))
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "test"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()
    client.put(f"/tasks/{task['id']}/draft", json={"markdown": "# Draft\n\nBody\n"})

    response = client.post(f"/sessions/{session['id']}/artifacts/export-pdf")

    assert response.status_code == 200
    assert response.json()["artifact_path"].endswith(".pdf")
    assert (Path(task["workspace_root"]) / response.json()["artifact_path"]).read_bytes().startswith(b"%PDF-")
    timeline = client.get(f"/sessions/{session['id']}/timeline").json()
    assert any(event["kind"] == "export_pdf" for event in timeline)
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest services/api/tests/test_phase3_api.py::test_export_docx_route_creates_artifact_without_runtime_prompt services/api/tests/test_phase3_api.py::test_export_pdf_route_creates_artifact_without_runtime_prompt -q
```

Expected: FAIL with 404 for new routes.

- [ ] **Step 3: Implement export helper route function**

In `services/api/docagent_api/routes/sessions.py`, import:

```python
from docagent_conversion import export_markdown_to_docx, export_markdown_to_pdf
```

Add helper inside `create_sessions_router`:

```python
    def _export_artifact(session_id: str, kind: str) -> dict[str, Any]:
        session = require_session(state, session_id)
        task = require_task(state, session["task_id"])
        workspace = Path(task["workspace_root"])
        source = workspace / "draft" / "draft.md"
        if not source.is_file():
            raise HTTPException(status_code=400, detail="Draft does not exist.")
        output = workspace / "artifacts" / f"{task['id']}-draft.{kind}"
        if kind == "docx":
            export_markdown_to_docx(source, output)
            event_kind = SemanticEventKind.EXPORT_DOCX
            summary = "Export DOCX"
        elif kind == "pdf":
            export_markdown_to_pdf(source, output)
            event_kind = SemanticEventKind.EXPORT_PDF
            summary = "Export PDF"
        else:
            raise HTTPException(status_code=400, detail="Unsupported export kind")
        artifact_path = output.relative_to(workspace).as_posix()
        event = manual_event(
            task["id"],
            session_id,
            f"export-{kind}-{uuid4().hex[:8]}",
            TimelineActor.SYSTEM,
            event_kind,
            summary,
            [artifact_path],
        )
        state.append_timeline_event(session_id, asdict(event))
        append_acp_projection_event(state, session_id, event)
        return {"session_id": session_id, "artifact_path": artifact_path, "event_count": 1}
```

Add routes near `export_markdown`:

```python
    @router.post("/sessions/{session_id}/artifacts/export-docx", response_model=LoopActionResponse)
    def export_docx(session_id: str) -> dict[str, Any]:
        return _export_artifact(session_id, "docx")


    @router.post("/sessions/{session_id}/artifacts/export-pdf", response_model=LoopActionResponse)
    def export_pdf(session_id: str) -> dict[str, Any]:
        return _export_artifact(session_id, "pdf")
```

- [ ] **Step 4: Run focused export route tests**

Run:

```powershell
python -m pytest services/api/tests/test_phase3_api.py::test_export_docx_route_creates_artifact_without_runtime_prompt services/api/tests/test_phase3_api.py::test_export_pdf_route_creates_artifact_without_runtime_prompt -q
```

Expected: PASS.

- [ ] **Step 5: Update smoke to use product DOCX export**

In `tools/runtime/openhands_smoke.py`, after the existing Markdown export call, add:

```python
    client.post(f"/sessions/{session['id']}/artifacts/export-docx").raise_for_status()
    print("exported docx")
```

- [ ] **Step 6: Commit Task 7**

```powershell
git add services/api/docagent_api/routes/sessions.py services/api/tests/test_phase3_api.py tools/runtime/openhands_smoke.py
git commit -m "feat: export docx and pdf artifacts"
```

## Task 8: Add Frontend Export Commands

**Files:**
- Modify: `apps/web/src/api.ts`
- Modify: `apps/web/src/shell/conversation/slashCommands.ts`
- Modify: `apps/web/src/shell/conversation/__tests__/slashCommands.test.ts`
- Modify: `apps/web/src/shell/__tests__/AppShell.test.tsx`

- [ ] **Step 1: Add failing slash command tests**

In `slashCommands.test.ts`, add:

```ts
it("runs docx and pdf export commands", async () => {
  vi.mocked(api.exportDocx).mockResolvedValue({ session_id: "s1", artifact_path: "artifacts/task-draft.docx" });
  vi.mocked(api.exportPdf).mockResolvedValue({ session_id: "s1", artifact_path: "artifacts/task-draft.pdf" });
  const context = commandContext({ activeSession: { id: "s1", status: "draft_ready" }, activeTask: taskRecord() });

  await executeSlashCommand("/export-docx", context);
  await executeSlashCommand("/export-pdf", context);

  expect(api.exportDocx).toHaveBeenCalledWith("s1");
  expect(api.exportPdf).toHaveBeenCalledWith("s1");
});
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
cd apps/web
npm run test:unit -- --run src/shell/conversation/__tests__/slashCommands.test.ts src/shell/__tests__/AppShell.test.tsx
```

Expected: FAIL because `exportDocx` and `exportPdf` are missing.

- [ ] **Step 3: Add API methods**

In `apps/web/src/api.ts`, add:

```ts
exportDocx: (sessionId: string) =>
  request<LoopActionResult>(`/sessions/${sessionId}/artifacts/export-docx`, { method: "POST" }),
exportPdf: (sessionId: string) =>
  request<LoopActionResult>(`/sessions/${sessionId}/artifacts/export-pdf`, { method: "POST" }),
```

- [ ] **Step 4: Add slash commands**

In `slashCommands.ts`, add:

```ts
  if (command === "/export-docx") {
    const result = await api.exportDocx(session.id);
    await Promise.all([context.refreshTimeline(), context.refreshWorkspace(), context.refreshSessions?.()]);
    if (result.artifact_path) await context.openArtifact(result.artifact_path);
    return { handled: true, message: "DOCX export created." };
  }
  if (command === "/export-pdf") {
    const result = await api.exportPdf(session.id);
    await Promise.all([context.refreshTimeline(), context.refreshWorkspace(), context.refreshSessions?.()]);
    if (result.artifact_path) await context.openArtifact(result.artifact_path);
    return { handled: true, message: "PDF export created." };
  }
```

Add to `SLASH_COMMANDS`:

```ts
{ command: "/export-docx", description: "Export DOCX artifact" },
{ command: "/export-pdf", description: "Export PDF artifact" },
```

- [ ] **Step 5: Run frontend tests**

Run:

```powershell
cd apps/web
npm run test:unit -- --run src/shell/conversation/__tests__/slashCommands.test.ts src/shell/__tests__/AppShell.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit Task 8**

```powershell
git add apps/web/src/api.ts apps/web/src/shell/conversation/slashCommands.ts apps/web/src/shell/conversation/__tests__/slashCommands.test.ts apps/web/src/shell/__tests__/AppShell.test.tsx
git commit -m "feat: add docx pdf export commands"
```

## Task 9: Sync Documentation And Final Verification

**Files:**
- Modify: `docs/architecture/markdown-pipeline.md`
- Modify: `docs/architecture/event-model.md`
- Modify: `docs/index.md`
- Modify: `tools/import/README.md`
- Modify: `README.md`

- [ ] **Step 1: Update docs with implementation facts**

In `docs/architecture/markdown-pipeline.md`, add an implementation status section:

```markdown
## Implementation Status

The product import/export boundary supports text, Markdown, HTML, DOCX, and
digital PDF as conversion inputs. Internally, converted resources are still
Markdown plus assets and conversion reports. DOCX and PDF are retained as
originals or exported artifacts only.

DOCX and PDF export read `draft/draft.md` and write files under `artifacts/`.
They do not make DOCX or PDF editable workspace formats.
```

In `docs/architecture/event-model.md`, add export rows:

```markdown
| backend export route writes `artifacts/*.docx` | Export DOCX |
| backend export route writes `artifacts/*.pdf` | Export PDF |
```

Insert the rows in the `## Semantic Projections` examples table immediately
after:

```markdown
| run `export_docx.py` | Export DOCX |
```

In `docs/index.md`, add the new spec:

```markdown
- `superpowers/specs/2026-05-17-markdown-import-export-pipeline-design.md`: import/export boundary design for Word/PDF while keeping Markdown internal.
```

In `README.md`, under `Current active work should preserve the original product
boundary while closing implementation gaps:`, replace:

```markdown
- make import, conversion reports, export, and skill-pack versioning durable;
```

with:

```markdown
- keep Markdown as the only internal format while supporting Word/PDF at import and export boundaries;
- make conversion reports, export artifacts, and skill-pack versioning durable;
```

- [ ] **Step 2: Run final backend verification**

Run:

```powershell
python -m pytest packages/conversion/tests tools/import/tests packages/contracts/tests services/api/tests agent/runtime-adapters/mock/tests -q
```

Expected: PASS.

- [ ] **Step 3: Run final frontend verification**

Run:

```powershell
cd apps/web
npm run test:unit -- --run
npm run test
npm run build
```

Expected: PASS. Existing Vite large-chunk warning is acceptable.

- [ ] **Step 4: Run concrete documentation/file structure checks**

Run:

```powershell
$required = @(
  "packages/conversion/docagent_conversion/importers.py",
  "packages/conversion/docagent_conversion/exporters.py",
  "tools/export/export_docx.py",
  "tools/export/export_pdf.py",
  "docs/superpowers/specs/2026-05-17-markdown-import-export-pipeline-design.md",
  "docs/superpowers/plans/2026-05-17-markdown-import-export-pipeline.md"
)
$missing = $required | Where-Object { -not (Test-Path $_) }
if ($missing) { throw "Missing required files: $($missing -join ', ')" }
Get-ChildItem -Recurse -File | Select-Object FullName | Measure-Object | Out-Null
```

Expected: exit code 0 and no missing-file exception.

- [ ] **Step 5: Commit docs**

```powershell
git add README.md docs/architecture/markdown-pipeline.md docs/architecture/event-model.md docs/index.md tools/import/README.md
git commit -m "docs: sync markdown import export pipeline"
```

## Final Verification

After all tasks are complete, run:

```powershell
python -m pytest packages/conversion/tests tools/import/tests packages/contracts/tests services/api/tests agent/runtime-adapters/mock/tests -q
cd apps/web
npm run test:unit -- --run
npm run test
npm run build
cd ..\..
$required = @(
  "packages/conversion/docagent_conversion/importers.py",
  "packages/conversion/docagent_conversion/exporters.py",
  "tools/export/export_docx.py",
  "tools/export/export_pdf.py"
)
$missing = $required | Where-Object { -not (Test-Path $_) }
if ($missing) { throw "Missing required files: $($missing -join ', ')" }
git status --short --branch
```

Expected:

- Python suite passes.
- Frontend unit, e2e, and build pass.
- Documentation structure check exits 0.
- Worktree contains only intentional changes or is clean after commits.

## Rollback Notes

- If multipart upload causes runtime dependency problems, revert Task 3 and Task 4 while keeping Task 1 and Task 2. Text import remains functional through the shared conversion helper.
- If DOCX/PDF export artifacts fail in downstream consumers, revert Task 7 and Task 8. The import boundary remains useful independently.
- If `pypdf` causes install issues, pause before changing behavior because this plan treats digital PDF import as part of the accepted MVP boundary. Keep DOCX support and file a dependency/runtime fix rather than silently downgrading PDF support.

## Deferred Product Decisions

- Exported DOCX/PDF artifacts use workspace paths plus ACP/projection events for this pass. Add an artifact database table later only if artifact history, permissions, or retention policy require it.
- Exported artifact filenames use task id for deterministic paths.
- PDF import succeeds only when text extraction returns non-empty content. Empty extraction writes a failed conversion report and keeps the original.
