# Markdown Import Export Pipeline Design

## Status

Accepted for implementation. This spec captures the accepted direction for closing the
gap where current import/export implementation is narrower than the Markdown
pipeline contract.

## Reader And Action

Reader: an engineer or agent planning product-grade import and export boundary
work for DocAgent Workbench.

Post-read action: write or execute an implementation plan that keeps Markdown
as the only internal document format while adding Word and PDF support at the
import and export boundaries.

## Context

DocAgent Workbench is a document-version Claude Code workbench. The agent edits
an inspectable workspace, and the workspace contract says drafts, context,
converted inputs, reviews, and checkpoints are Markdown or text. The Markdown
pipeline contract already says external resources are converted at boundaries:

- import boundary: Word, PDF, HTML, text, and later other office/image formats
  become normalized Markdown plus assets and conversion reports;
- internal boundary: Markdown only;
- export boundary: Markdown becomes Word or PDF artifacts.

Current implementation is narrower:

- `tools/import/convert_to_markdown.py` supports only `.md`, `.markdown`, and
  `.txt`, with unsupported files producing a failed report;
- API authoring import is only `/tasks/{task_id}/inputs/text`;
- Skill Pack resources are only pasted text;
- the frontend composer reads attachments with `file.text()`, which is wrong
  for binary Word and PDF files;
- `tools/export/` has no working exporter;
- `/sessions/{session_id}/artifacts/export-markdown` asks the runtime to write
  a Markdown artifact instead of using a product export tool.

This gap is visible in the repo-alignment audit. It should be closed without
turning the editor into a Word/PDF editor and without making conversion
invisible.

## Goals

- Preserve Markdown as the only internal authoring and Skill Creator format.
- Support Word and PDF as import boundary formats.
- Support Word and PDF as export boundary formats.
- Store original imports, converted Markdown, extracted assets, and conversion
  reports in the existing workspace layout.
- Make conversion status and warnings visible to users and agents.
- Reuse one conversion boundary for authoring inputs and Skill Pack materials.
- Produce export artifacts under `artifacts/` with explicit kind and status.
- Keep unsupported or failed conversions auditable instead of silently dropping
  files.

## Non-Goals

- Do not edit DOCX or PDF directly inside the workspace.
- Do not make high-fidelity Word layout reproduction a requirement for MVP.
- Do not make PDF import depend on OCR-heavy engines in the first pass.
- Do not introduce semantic RAG as the default way to use converted resources.
- Do not let agents read original binary files as normal context.
- Do not require a perfect production converter before the product boundary is
  represented in API, UI, reports, and tests.

## Product Boundary

### Internal Format

The internal format remains Markdown. That includes:

- `brief.md`;
- `inputs/markdown/*.md`;
- `context/*.md`;
- `draft/outline.md`;
- `draft/draft.md`;
- `reviews/*.md`;
- generated Skill Pack artifacts such as `SKILL.md`, checklist Markdown/YAML,
  and notes.

DOCX and PDF files may be stored only as:

- originals under `inputs/original/` or draft pack `resources/original/`;
- exported artifacts under `artifacts/`;
- export references for future style guidance.

They are not editable workspace state.

### Import Boundary

Every uploaded or pasted resource should produce a resource result:

- original source path;
- Markdown path when conversion succeeds;
- asset directory when assets are extracted;
- conversion report path;
- MIME type;
- original filename;
- status.

For MVP, support:

- `.md` and `.markdown`: direct normalize/copy;
- `.txt`: wrap as Markdown text;
- `.html` and `.htm`: convert to Markdown with a lightweight local parser or
  simple text extraction;
- `.docx`: convert to Markdown with a narrow built-in ZIP/XML text extractor;
- `.pdf`: convert digital PDF text to Markdown with `pypdf`.

The key product rule is that DOCX/PDF are supported boundary formats and
produce visible reports. Malformed, encrypted, or image-only PDF files may
fail conversion in MVP, but they must keep originals, write failed reports, and
must not be treated as usable Markdown context.

### Export Boundary

The export boundary starts from `draft/draft.md` and creates artifacts:

- DOCX: valid Word document artifact generated from Markdown text;
- PDF: valid PDF artifact generated from Markdown text.

The backend owns export actions because export is a product boundary, not an
agent reasoning task. The runtime may request export, but the conversion itself
should happen through fixed tools or backend services.

## Conversion Report Contract

Use the existing `ConversionReport` shape from `packages/contracts/schemas.md`
as the stable contract:

```yaml
source_path: string
markdown_path: string | null
asset_dir: string | null
engine: docling | markitdown | pandoc | mineru | marker | manual | unknown
status: succeeded | succeeded_with_warnings | failed
warnings:
  - type: string
    message: string
    location: string | null
features_detected:
  tables: number
  images: number
  formulas: number
  footnotes: number
  pages: number | null
created_at: IsoDateTime
```

Additional implementation fields may be added only if they are optional and
documented. Report paths returned from product APIs should be workspace-relative
or pack-draft-relative, never arbitrary host paths.

## Architecture

### Shared Conversion Module

Introduce `packages/conversion` as a shared, backend-neutral conversion module
that can write into either a task input root or a Skill Pack resource root.

Responsibilities:

- safe filename normalization and unique path allocation;
- write original bytes or pasted text;
- call a converter based on file extension and MIME type;
- write Markdown and assets when conversion succeeds;
- write a report for success, warning, unsupported, or failure;
- return a stable resource result for API responses.

The current `services/api/docagent_api/imports.py` and
`services/api/docagent_api/skill_packs.py` should stop duplicating conversion
layout logic. They should call this module instead.

### Tool Layer

Keep `tools/import/convert_to_markdown.py` as a CLI wrapper around the same
conversion behavior, or keep it behavior-compatible with the backend module.

Create export tools:

- `tools/export/export_docx.py`;
- `tools/export/export_pdf.py`.

The tools should be deterministic and safe for agents to call. They should take
explicit source and output paths and should not infer arbitrary workspace paths.

For MVP, prefer a lightweight implementation that produces valid artifacts in
test environments:

- DOCX import/export uses built-in ZIP/XML handling for paragraph text;
- PDF import uses `pypdf` for digital text extraction;
- PDF export uses a small built-in text PDF writer.

If the implementation adds dependencies such as `python-docx`, `pypandoc`,
`markitdown`, `pypdf`, or an HTML/PDF renderer, it must update `pyproject.toml`
and keep Docker/dev startup implications explicit.

### API Boundary

Authoring API should expose:

- `POST /tasks/{task_id}/inputs/text` as a compatibility wrapper;
- `POST /tasks/{task_id}/inputs/files` for multipart uploads;
- `POST /sessions/{session_id}/artifacts/export-docx`;
- `POST /sessions/{session_id}/artifacts/export-pdf`.

Skill Pack API should expose:

- existing `POST /skill-packs/{pack_id}/resources/text` as a compatibility
  wrapper;
- `POST /skill-packs/{pack_id}/resources/files` for multipart uploads into a
  selected resource group.

Both authoring and Skill Pack file uploads should reuse the same conversion
engine and report contract.

### UI Boundary

Authoring composer attachments should upload `File` objects through `FormData`.
The UI should no longer call `file.text()` for every attachment.

The authoring surface should show:

- attached filename;
- conversion status;
- warnings or failure messages;
- Markdown path when available;
- clear indication that failed conversions are not sent to the agent as
  Markdown context.

The Skill Pack management surface should support file upload as well as pasted
text resources. Resource rows should show group, filename, status, and warning
visibility.

Export controls should distinguish Markdown, DOCX, and PDF. `/export` may keep
Markdown as the default command for compatibility, but the UI should expose
Word and PDF exports explicitly once the routes exist.

## Runtime And Agent Rules

Agents should read:

- converted Markdown files;
- conversion reports;
- export artifacts only when explicitly asked for export troubleshooting.

Agents should not read:

- original binary imports;
- DOCX/PDF outputs as source context;
- failed resources as if they were available converted content.

Prompts should preserve the existing rule that originals are retained for audit
and re-conversion only.

## Error Handling

Import failures should:

- keep the original file;
- write a conversion report;
- return a non-`converted` status;
- omit `markdown_path`;
- include a user-facing warning or error;
- avoid creating timeline/user-message attachments that imply usable Markdown
  context.

Export failures should:

- avoid writing partial artifacts as successful outputs;
- write an export report or return structured failure detail;
- emit an error projection or failed artifact status;
- preserve the session state when export fails.

## Rollout

1. Introduce shared conversion data shapes and helper module.
2. Port authoring text import and Skill Pack text resource import to the shared
   helper without changing user behavior.
3. Add multipart upload routes for authoring and Skill Pack resources.
4. Update frontend attachment/resource upload paths to use files and show
   conversion status.
5. Add DOCX export tool and backend route.
6. Add PDF export tool and backend route with the built-in text PDF writer.
7. Sync docs and verification commands.

Each stage should leave the current authoring loop and Skill Creator workflow
usable.

## Testing Strategy

Backend tests should cover:

- text/Markdown conversion success;
- HTML conversion success or warning behavior;
- DOCX and digital PDF upload produce Markdown plus reports and never treat
  binary bytes as text;
- failed conversion keeps original and omits `markdown_path`;
- authoring upload appends a conversion timeline/projection event;
- Skill Pack file upload stores resource metadata and reports;
- DOCX export writes a valid artifact path;
- PDF export writes a valid artifact path.

Frontend tests should cover:

- composer uploads a `File` through the file API instead of `file.text()`;
- failed conversion is visible and not passed as a message attachment;
- Skill Pack management upload displays resource status;
- export controls call the correct DOCX/PDF API routes.

Tool tests should cover:

- CLI import reports for supported and unsupported formats;
- DOCX export command creates an output file from Markdown;
- PDF export command creates an output file from Markdown.

## Deferred Product Decisions

- Exported DOCX/PDF artifacts use workspace paths plus ACP/projection events
  for this pass. A later artifact database table can be added if artifact
  history, permissions, or retention policy require it.
