# DocAgent Workbench

DocAgent Workbench is a document-agent workbench inspired by Claude Code and OpenHands. It lets users collaborate with an agent inside a document workspace: provide a brief, upload materials, configure best-practice examples and writing rules, interrupt the agent, review its process, revise locally, run checklists, and export final documents.

The project goal is a general document coding-agent experience, not a fixed workflow builder or a template-per-document-type generator.

## Repository Map

| Path | Purpose |
|---|---|
| `AGENTS.md` | Instructions for AI agents working in this repo. |
| `ARCHITECTURE.md` | High-level system boundaries and dependency direction. |
| `PLANS.md` | How execution plans are written and tracked. |
| `docs/` | Current design truth: product, architecture, decisions, plans, quality. |
| `reference/` | Research notes and earlier specs. Useful context, not always current truth. |
| `apps/web/` | React document workbench UI. |
| `services/api/` | FastAPI backend, product state, and agent runtime adapter. |
| `packages/` | Shared contracts, workspace helpers, doctype pack helpers, timeline mapping. |
| `agent/` | System prompts, skill guidance, and runtime adapter notes. |
| `tools/` | Fixed workspace, export, and repository scripts. |
| `doc-types/` | Seed document type packs, starting with PRD. |
| `tests/` | Cross-cutting tests once implementation begins. |

## Local Startup

On Windows, start the Phase 1 API and web app together with:

```powershell
.\start-dev.cmd
```

The script starts FastAPI on `http://127.0.0.1:8000`, Vite on `http://127.0.0.1:5173`, and writes logs under `.local/dev/`.

## Phase 0 Focus

Phase 0 validates the document-version Claude Code loop:

1. Create a task workspace.
2. Read a user brief and optional uploaded materials.
3. Read a document type `SKILL.md`, examples, specs, and checklist.
4. Extract structure and style notes from best-practice examples.
5. Propose an outline and wait for user confirmation.
6. Draft, checkpoint, revise locally, and update context files.
7. Run a checklist and export DOCX.
8. Show a semantic timeline of what the agent did.

Phase 0 intentionally does not build RAG, complex RBAC, high-fidelity export, or a workflow designer.

## Current Design Sources

- `reference/spec_v0_1.md`: original broad platform vision.
- `reference/spec_review_rapid_prototype_v3.md`: current rapid prototype direction.
- `docs/product/vision.md`: curated current product intent.
- `docs/product/ui-surfaces.md`: management and authoring UI design.
- `docs/architecture/workspace-contract.md`: workspace contract every agent task must follow.
- `docs/architecture/markdown-pipeline.md`: Markdown-only import/internal/export strategy.
