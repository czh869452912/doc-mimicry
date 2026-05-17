from __future__ import annotations

import html
import textwrap
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


def _simple_pdf_bytes(lines: list[str]) -> bytes:
    page_streams: list[bytes] = []
    rendered: list[str] = []
    y = 760
    for line in lines:
        for wrapped in textwrap.wrap(line, width=88) or [""]:
            safe = wrapped.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            rendered.append(f"BT /F1 11 Tf 50 {y} Td ({safe}) Tj ET")
            y -= 16
            if y < 60:
                page_streams.append("\n".join(rendered).encode("latin-1", errors="replace"))
                rendered = []
                y = 760
    if rendered or not page_streams:
        page_streams.append("\n".join(rendered).encode("latin-1", errors="replace"))

    page_count = len(page_streams)
    font_object_number = 3 + page_count * 2
    page_object_numbers = [3 + index * 2 for index in range(page_count)]
    content_object_numbers = [4 + index * 2 for index in range(page_count)]
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        (
            b"<< /Type /Pages /Kids "
            + b"[" + b" ".join(f"{number} 0 R".encode("ascii") for number in page_object_numbers) + b"]"
            + f" /Count {page_count} >>".encode("ascii")
        ),
    ]
    for page_number, content_number in zip(page_object_numbers, content_object_numbers):
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font_object_number} 0 R >> >> /Contents {content_number} 0 R >>".encode("ascii")
        )
        stream = page_streams[(page_number - 3) // 2]
        objects.append(b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream")
    objects.append(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    )
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
