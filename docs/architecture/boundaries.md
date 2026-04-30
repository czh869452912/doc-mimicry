# Architecture Boundaries

## UI Boundary

The UI displays and controls work. It should not decide writing strategy.

Owns:

- Document type dashboards.
- Resource upload and conversion review.
- Skill Creator interaction surface.
- Chat input and transcript.
- Timeline rendering.
- Draft preview and diff.
- Version list.
- Approval and export actions.

Does not own:

- Agent prompts.
- Workspace file rules.
- Runtime-specific API details.

## Backend Boundary

The backend owns product state and integration.

Owns:

- Tasks.
- Document type registration.
- Uploaded resource storage and conversion orchestration.
- Workspace initialization.
- Session lifecycle.
- Versions and artifacts.
- Audit records.
- Timeline semantic enrichment.

Does not own:

- Drafting decisions.
- Per-document workflow logic.
- Best-practice interpretation.

## Import/Export Boundary

Import/export code owns file format conversion.

Owns:

- Original uploaded files.
- Markdown conversion outputs.
- Conversion reports and warnings.
- Markdown-to-DOCX/PDF export.

Does not own:

- Agent drafting strategy.
- Document type workflow logic.
- Hidden automatic rewriting of converted Markdown without user visibility.

## Agent Boundary

The agent owns reasoning and document changes inside the workspace.

Owns:

- Reading examples and specs.
- Extracting structure and style notes.
- Proposing plans.
- Writing and revising drafts.
- Running checklists according to skill guidance.

Does not own:

- User/team permissions.
- Permanent artifact storage.
- Cross-task access.
- Product audit truth.

## Package Boundary

Shared packages contain reusable schemas and helpers. They should not import from apps or services.
