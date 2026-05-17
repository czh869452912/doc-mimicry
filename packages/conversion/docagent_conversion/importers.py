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
    suffix = Path(original_filename).suffix.lower()
    stem = _unique_stem(layout, _safe_stem(original_filename), suffix)
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
            warnings.append(
                {
                    "type": "html_format_loss",
                    "message": "HTML styling was reduced to Markdown text.",
                    "location": None,
                }
            )
        elif suffix == ".docx":
            markdown = _docx_to_markdown(content)
            warnings.append(
                {
                    "type": "docx_format_loss",
                    "message": "DOCX layout and styling were reduced to Markdown text.",
                    "location": None,
                }
            )
        elif suffix == ".pdf":
            engine = "pypdf"
            markdown, page_count = _pdf_to_markdown(content)
            features["pages"] = page_count
            warnings.append(
                {
                    "type": "pdf_format_loss",
                    "message": "PDF layout was reduced to extracted text.",
                    "location": None,
                }
            )
        else:
            warnings.append(
                {
                    "type": "unsupported_format",
                    "message": f"Unsupported import format: {suffix or 'no extension'}.",
                    "location": None,
                }
            )
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
