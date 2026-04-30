# Agent Instructions

This repository is designed to be worked on by AI coding agents and humans together.

## Product North Star

Build a document-version of Claude Code: an interactive, observable, human-in-the-loop agent workbench for writing and revising enterprise documents from user briefs, uploaded materials, best-practice examples, specifications, and checklists.

This is not a fixed workflow builder, template generator, or semantic RAG writing app.

## Start Here

1. Read `README.md` for the repository map.
2. Read `ARCHITECTURE.md` for system boundaries.
3. Read `docs/product/vision.md` for product intent.
4. Read `docs/product/ui-surfaces.md` before touching user-facing flows.
5. Read `docs/architecture/workspace-contract.md` before touching agent workspace logic.
6. Read `docs/architecture/markdown-pipeline.md` before touching import/export or document parsing.
7. Read `PLANS.md` before starting a multi-step change.

## Working Rules

- Keep the repo agent-readable: small files, clear boundaries, explicit contracts.
- Prefer updating docs when decisions change. Do not leave important architecture only in chat.
- Do not turn the product into a fixed DAG workflow or per-doc-type template system.
- Keep RAG optional and secondary. Best-practice examples are mainly for structure, style, and organization.
- Preserve the coding-agent feel: free conversation, user interrupts, iterative edits, context files, checkpoints, observable actions.
- Keep Markdown as the only internal document format. Convert at import/export boundaries.
- Keep management and authoring as separate UI surfaces.
- Treat `reference/` as research/history and `docs/` as current project truth.

## Directory Boundaries

- `apps/web`: React document workbench UI.
- `services/api`: FastAPI product backend and agent runtime adapter.
- `packages/contracts`: shared schemas and event contracts.
- `packages/workspace`: workspace contract helpers.
- `packages/doctypes`: document type pack metadata and validation.
- `packages/timeline`: raw agent event to semantic timeline mapping.
- `agent`: prompts, skills, runtime adapter notes, and agent-facing behavior.
- `tools`: fixed scripts callable by agents or CI.
- `doc-types`: seed document type packs.
- `docs`: current design, decisions, plans, and quality guidance.
- `reference`: source research and early specs.

## Verification

When code exists, add the smallest meaningful verification command to the relevant README or plan before claiming completion.

For documentation-only changes, run a quick structure check with:

```powershell
Get-ChildItem -Recurse -File | Select-Object FullName
```
