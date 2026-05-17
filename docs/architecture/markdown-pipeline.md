# Markdown Pipeline

DocAgent Workbench uses Markdown as the only internal document format.

All imported resources are normalized to Markdown before agent use. All drafts are authored and revised as Markdown. Other formats exist only at import or export boundaries.

## Contract

```text
Import boundary:
  DOCX / PDF / PPTX / XLSX / images / HTML / text
    -> normalized Markdown + assets + conversion report

Internal boundary:
  Markdown only

Export boundary:
  Markdown
    -> DOCX / PDF
```

Current implementation supports Markdown, text, HTML, DOCX, and digital-text
PDF at the import boundary. Unsupported formats keep the original file and
write a failed conversion report instead of becoming agent context.

Current export support creates DOCX and PDF artifacts from `draft/draft.md`
through fixed backend/CLI tools. The editor still treats Markdown as the only
editable draft state.

## Why Markdown

- Agents can read and edit it reliably.
- Diffs are simple.
- Checkpoints are cheap.
- Workspace context is inspectable.
- Export can be handled by fixed tools.
- UI can support source editing, preview, and paragraph selection.

## Imported Resource Layout

Task inputs should be stored as:

```text
inputs/
  original/
    uploaded-file.docx
  markdown/
    uploaded-file.md
  assets/
    uploaded-file/
      image-001.png
  reports/
    uploaded-file.conversion.json
```

Document type resources should follow the same idea:

```text
doc-types/{doc_type}/
  examples/
    original/
    markdown/
    assets/
    reports/
  specs/
    original/
    markdown/
    assets/
    reports/
  checklists/
  export-references/
```

Phase 0 can keep seed resources simple, but the architecture should not assume that uploaded files are already Markdown.

## Conversion Report

Every import should produce a machine-readable conversion report.

Suggested fields:

```json
{
  "source_path": "inputs/original/example.docx",
  "markdown_path": "inputs/markdown/example.md",
  "asset_dir": "inputs/assets/example",
  "engine": "docling",
  "status": "succeeded",
  "warnings": [
    {
      "type": "table_complexity",
      "message": "Merged cells were flattened."
    }
  ],
  "features_detected": {
    "tables": 4,
    "images": 7,
    "formulas": 2,
    "footnotes": 0
  }
}
```

The UI should show warnings before a converted resource is used in Skill Creator or authoring.

## Conversion Engine Strategy

Use a multi-engine pipeline rather than betting on one converter. The current
MVP uses a lightweight local converter so the product boundary is represented
in API, UI, reports, and tests before heavier conversion services are added.

### Current MVP Engines

- Markdown and text: manual normalization.
- HTML: local text extraction with a format-loss warning.
- DOCX: built-in ZIP/XML paragraph extraction with a format-loss warning.
- PDF: `pypdf` digital text extraction with a format-loss warning.
- DOCX export: built-in minimal WordprocessingML package writer.
- PDF export: built-in text PDF writer.

### Future Default Engine: Docling

Docling is the default candidate for broader import coverage because it targets local document conversion and supports formats such as PDF, DOCX, PPTX, images, HTML, and Markdown. It can produce structured document output and Markdown, making it suitable for offline enterprise use.

### Lightweight Office Fallback: MarkItDown Or Pandoc

Use MarkItDown or Pandoc as fallback for simple Office, HTML, and text resources when speed and simplicity matter more than layout fidelity.

### Complex PDF Fallback: MinerU Or Marker

Use MinerU or Marker for complex PDFs, especially when formula, table, OCR, and academic-style layout fidelity matter.

### Future Export: Pandoc And LibreOffice

Use Pandoc as the primary Markdown-to-DOCX exporter, with optional DOCX reference documents for styling. Use LibreOffice headless when PDF export or format normalization requires it.

## Selection Policy

Initial policy:

| Input | Preferred path |
|---|---|
| Markdown / text | direct normalize |
| DOCX | Docling, fallback Pandoc/MarkItDown |
| PDF simple digital | Docling |
| PDF complex / scanned / formula-heavy | Docling first, fallback MinerU or Marker |
| PPTX | Docling or MarkItDown |
| images | Docling/OCR path |
| HTML | MarkItDown or Pandoc |

The conversion service should keep the original file and report which engine was used.

## Formula, Table, And Image Handling

Markdown cannot perfectly preserve every original layout. The system should prefer an inspectable approximation plus explicit warnings over silent loss.

Guidelines:

- Use GitHub-Flavored Markdown tables for simple tables.
- Preserve complex tables as HTML blocks or extracted images when Markdown tables would be misleading.
- Preserve formulas as LaTeX-style math when possible.
- Save images into `assets/` and link them from Markdown.
- For uncertain OCR or layout interpretation, mark warnings in the conversion report.

## UI Implications

Management interface:

- Show original file, converted Markdown, assets, and warnings.
- Allow users to accept, reject, or re-run conversion with another engine.
- Skill Creator should read converted Markdown and conversion reports.

Authoring interface:

- Workspace tree should separate original files from converted Markdown.
- Agent should read Markdown, not original binary documents.
- Preview should render Markdown, tables, images, math, and warnings where useful.

## Non-Goals

- Perfect Word layout preservation inside the editor.
- Editing DOCX directly.
- Treating conversion as invisible magic.
- Making RAG the default way to use converted resources.

