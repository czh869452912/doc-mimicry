# Contracts Package

Shared schemas and types for UI, API, tools, and ACP runtime adapters.

Current minimal schema source:

- `schemas.md`

Expected contracts:

- Task.
- Session.
- Workspace.
- Document type pack.
- ACP event envelope.
- ACP runtime update.
- Semantic projection.
- Approval.
- Artifact.
- Imported resource.
- Conversion report.
- Markdown asset.

## Phase 0 Python Models

The first executable contract models live in `docagent_contracts/models.py`.

These models intentionally use the Python standard library so Phase 0 can start without dependency decisions. If generated TypeScript or Pydantic models are added later, keep field names aligned with `schemas.md`.
