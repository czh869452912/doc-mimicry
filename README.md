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
| `services/api/` | FastAPI backend, product state, ACP event log, and agent runtime adapter. |
| `packages/` | Shared ACP contracts, workspace helpers, doctype pack helpers, and projection helpers. |
| `agent/` | System prompts, skill guidance, and runtime adapter notes. |
| `tools/` | Fixed workspace, export, and repository scripts. |
| `doc-types/` | Seed document type packs that bootstrap into versioned skill packs. |
| `tests/` | Cross-cutting tests once implementation begins. |

## Local Startup

On Windows, start the Phase 1 API and web app together with:

```powershell
.\start-dev.cmd
```

The script uses Docker Compose to start Postgres, Redis, FastAPI, the Celery worker, and Vite. FastAPI is available on `http://127.0.0.1:18000`, and the web app is available on `http://127.0.0.1:5173`.

To start the same stack with the OpenHands runtime adapter selected:

```powershell
.\start-dev.cmd -Runtime openhands-acp
```

The script starts the OpenHands Agent Server as a Docker Compose service,
exposes it on `http://127.0.0.1:18001`, and connects API/worker containers to it
through the ACP runtime adapter with the shared workspace volume mounted.
Provider-backed model traffic goes through LiteLLM at `http://litellm:4000`
with model aliases such as `docagent/default`, `docagent/fast`, and
`docagent/reasoning`. Set provider keys such as `OPENAI_API_KEY` or a
provider-specific `DOCAGENT_LITELLM_REASONING_API_KEY` only for live runtime
runs; mock runtime development does not need them.

To point OpenHands directly at an OpenAI-compatible provider instead of the
local LiteLLM gateway, include the LiteLLM provider prefix in `LLM_MODEL`:

```powershell
$env:LLM_API_KEY = "..."
$env:LLM_MODEL = "openai/kimi-k2-0905-preview"
$env:LLM_BASE_URL = "https://api.moonshot.cn/v1"
.\start-dev.cmd -Runtime openhands
```

To use the embedded upstream ACP client instead of DocAgent's local fallback
agent pane, add `-ExternalAcpUi`:

```powershell
.\start-dev.cmd -Runtime openhands-acp -ExternalAcpUi
```

Or set the same behavior in `.env`:

```dotenv
EXTERNAL_ACP_UI=true
ACP_UI_PORT=4173
VITE_ACP_UI_URL=
```

The script prepares the ignored `.local/reference/acp-ui` checkout, starts it
on `http://127.0.0.1:4173`, and builds the web app with that iframe URL.

Smoke-test the mock Docker Compose stack with:

```powershell
python tools/runtime/compose_smoke.py --runtime mock-acp
```

The OpenHands end-to-end smoke is opt-in and requires a reachable Agent Server plus LLM credentials:

```powershell
$env:DOCAGENT_RUNTIME = "openhands-acp"
$env:DOCAGENT_ACP_RUNTIME_URL = "http://127.0.0.1:18001"
$env:DATABASE_URL = "postgresql+psycopg2://docagent:docagent@localhost:5432/docagent"
python tools/runtime/openhands_smoke.py
```

## Current Implementation Focus

The original Phase 0 loop validated the document-version Claude Code shape:

1. Create a task workspace.
2. Read a user brief and optional uploaded materials.
3. Read a document type `SKILL.md`, examples, specs, and checklist.
4. Extract structure and style notes from best-practice examples.
5. Propose an outline and wait for user confirmation.
6. Draft, checkpoint, revise locally, and update context files.
7. Run a checklist and export DOCX.
8. Stream ACP events in the center timeline, with DocAgent-specific cards isolated behind ACP render slots.

The current implementation has moved beyond the first skeleton. Product-facing
agent interaction is ACP-first: the backend owns the ACP event log, the center
authoring surface reads `/sessions/{session_id}/events`, runtime selection uses
`mock-acp` or `openhands-acp`, and OpenHands model traffic is routed through
LiteLLM aliases when the real runtime is selected.

Document type guidance is now a versioned product object. Seed packs under
`doc-types/` bootstrap into draft/published skill packs, published snapshots are
immutable, and new authoring tasks bind to a published `pack_version_id` when
one exists. The Skill Creator management surface accepts pasted source
materials, lets the agent generate or revise `SKILL.md`, checklists, and notes,
keeps direct user edits as current artifact state, validates the draft, and
publishes a new version only by explicit user action.

Current active work should preserve the original product boundary while closing
implementation gaps:

- keep management and authoring as separate product surfaces;
- keep Markdown as the only internal document format;
- keep document type packs as skill guidance, not workflows or templates;
- use shared import/export boundaries for authoring materials and Skill Pack materials;
- keep originals, converted Markdown, conversion reports, and exported DOCX/PDF artifacts durable;
- keep active plans and reviews synchronized with live code.

## Current Design Sources

- `reference/spec_v0_1.md`: original broad platform vision (historical reference).
- `reference/spec_review_rapid_prototype_v3.md`: rapid prototype direction that shaped Phase 0–2.
- `docs/product/vision.md`: curated current product intent.
- `docs/product/ui-surfaces.md`: management and authoring UI design.
- `docs/superpowers/specs/2026-05-17-skill-creator-versioned-packs-design.md`: material-driven Skill Creator and versioned skill-pack design.
- `docs/decisions/2026-05-14-acp-interaction-plane-and-litellm-gateway.md`: canonical ACP interaction plane and LiteLLM gateway decision.
- `docs/architecture/event-model.md`: ACP event log and semantic projection contract.
- `docs/architecture/agent-runtime.md`: ACP runtime boundary and LiteLLM model gateway.
- `docs/product/phase-2-authoring-loop.md`: next version scope for the PRD authoring loop.
- `docs/architecture/workspace-contract.md`: workspace contract every agent task must follow.
- `docs/architecture/markdown-pipeline.md`: Markdown-only import/internal/export strategy.
- `docs/reviews/active/`: unresolved audit findings only.
- `docs/reviews/completed/`: archived review records and historical audit records.
- `docs/superpowers/completed/`: archived task-sized implementation plans and completion records.
