# Markdown Only Internal Format

## Context

DocAgent Workbench needs to accept many input formats: user text, DOCX, PDF, PPTX, images, screenshots, and other materials. It also needs to export to familiar formats such as DOCX and PDF.

The agent loop should remain simple and robust. Agents are strongest when reading and editing plain text formats with stable diffs and explicit file paths.

## Decision

Markdown is the only internal document format.

All imported files are converted to Markdown plus assets and conversion reports before agent use. Drafts, context files, examples, and specs are read and edited as Markdown. DOCX/PDF/PPTX/images exist at import and export boundaries only.

## Consequences

- The agent reads Markdown instead of binary Office/PDF files.
- The UI can provide Markdown source editing, preview, selection, diff, and export.
- Import quality becomes a first-class product concern.
- Conversion warnings must be visible to users.
- Complex tables, formulas, and image layouts require explicit preservation policies.

## Alternatives Considered

- Native DOCX editing: rejected for Phase 0 because it makes agent edits, diffs, and checkpoints harder.
- WYSIWYG document model as internal format: deferred because it adds complexity before validating the agent loop.
- Letting each runtime/tool read original binaries directly: rejected because it weakens auditability and repeatability.

