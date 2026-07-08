# Pi-Powered DocAgent Runtime Design

## Goal

Reframe DocAgent Workbench around Pi as the agent core and DocAgent as the
document workbench shell.

The target product remains a document-version Claude Code experience: users
bring a brief, materials, examples, specs, and checklists into a durable
workspace, then collaborate with an interruptible, observable agent to produce
and revise enterprise documents.

This design replaces the current OpenHands/ACP-first runtime direction with a
lighter Pi-centered architecture.

## Context

The current architecture made ACP the formal interaction plane and OpenHands the
first real runtime candidate. That created several mismatches:

- OpenHands is heavy for the document-authoring use case.
- The current OpenHands adapter is not a true durable ACP runtime; it keeps SDK
  conversations in process memory and cannot reliably rebind them across worker
  processes.
- ACP did not remove DocAgent's custom mapping burden. The system still carries
  ACP envelopes, semantic projections, raw OpenHands events, compatibility
  timeline rows, and frontend event heuristics.
- External ACP UI embedding risks making the center pane a generic agent client
  instead of a document workbench interaction surface.

Pi is a better fit as the agent core because it already owns the concerns
DocAgent should not reinvent:

- session lifecycle and JSONL session persistence;
- event streaming;
- abort, steer, and follow-up;
- tools, skills, prompt templates, and extensions;
- compaction and retry behavior;
- session trees, forks, labels, and branch summaries;
- SDK and RPC integration surfaces.

Observed Pi-based projects support this direction:

- OpenPi hosts Pi SDK in an app shell and keeps Pi responsible for agent
  semantics.
- pi-chat builds a domain bridge as a Pi extension with per-channel workspaces,
  memory, skills, and remote control.
- pi-review packages a domain workflow as Pi slash commands and extension
  behavior instead of a standalone workflow engine.
- pi-task and related packages add coordination through Pi tools and workspace
  artifacts rather than an external orchestration backend.

## Decision

DocAgent should become a Pi-powered document workbench.

Pi should own agent interaction semantics:

- prompt, steer, follow-up, abort;
- model selection and provider behavior;
- streaming events;
- tool execution;
- compaction;
- session tree and JSONL session history;
- skills, extensions, and prompt templates.

DocAgent should own document-product semantics:

- projects, tasks, and workspace creation;
- uploaded materials and conversion reports;
- document type skill packs and versioning;
- Markdown draft preview, source editing, diff, and checkpoints;
- DOCX/PDF export;
- artifact and workspace indexes;
- management UI for skill-pack creation and publishing;
- product-level audit and enterprise packaging.

Pi session JSONL should become the primary agent interaction record. DocAgent
may index Pi events and workspace files for UI queries, but it should avoid
duplicating Pi session history as a second source of truth.

## Non-Goals

- Do not turn DocAgent into a fixed DAG workflow builder.
- Do not make document type packs content templates.
- Do not keep ACP as the core authoring timeline contract.
- Do not wrap Pi behind another custom agent protocol unless a specific
  deployment boundary requires it.
- Do not migrate every feature at once. The first slice should prove the
  authoring loop only.

## Target Architecture

```text
DocAgent Web UI
  -> DocAgent Shell API
    -> Pi Runtime Host
      -> Pi SDK AgentSession
      -> DocAgent Pi Extension
      -> Task Workspace
      -> Skill Pack Context
```

The runtime host can initially be a Node service colocated with the product
backend. A subprocess RPC adapter remains a fallback for process isolation or a
Python-only deployment, but the preferred implementation is the Pi SDK because
it gives direct typed access to session events and lifecycle controls.

## Component Boundaries

### DocAgent Web UI

The UI remains the document workbench:

- left workspace/project/material navigation;
- center agent interaction surface;
- right Markdown preview/editor/diff/artifact surface;
- skill-pack management route.

The center pane should render a DocAgent-normalized view of Pi events, not raw
OpenHands payloads and not generic ACP rows. Product cards such as outline,
checkpoint, checklist, and artifact cards are projections from Pi events and
workspace changes.

### DocAgent Shell API

The shell API should become thinner than the current FastAPI runtime layer. It
keeps product authority around:

- task and skill-pack records;
- file import and conversion;
- workspace file index;
- draft and artifact metadata;
- export routes;
- user-facing audit queries.

It should stop owning agent state transitions such as `running_context`,
`await_outline_approval`, and `running_draft` as the core runtime truth. Those
states can remain as derived UI status labels.

### Pi Runtime Host

The runtime host creates and manages Pi sessions for DocAgent tasks.

Responsibilities:

- create or resume a Pi session for a task workspace;
- configure Pi `cwd` to the task workspace;
- inject DocAgent system prompt, current skill pack, and workspace contract;
- register DocAgent tools and extension commands;
- stream Pi events to the shell API or directly to the web UI through an
  authenticated channel;
- expose prompt, steer, follow-up, abort, compact, and session stats.

### DocAgent Pi Extension

DocAgent document behavior should be packaged as a Pi extension and project
resources rather than as a separate runtime adapter.

Initial tools and commands:

- read converted task materials;
- read skill-pack resources;
- write or patch Markdown drafts;
- create draft checkpoints;
- request outline approval;
- run checklist review;
- request DOCX/PDF export through the shell API or write export requests under
  workspace artifacts;
- report workspace contract violations.

Commands may include:

- `/start-outline`
- `/approve-outline`
- `/revise-selection`
- `/run-checklist`
- `/export-docx`
- `/export-pdf`

These commands are product shortcuts over conversational behavior, not a fixed
workflow DAG.

## Data Ownership

Pi owns:

- conversation history;
- streaming assistant/tool events;
- tool call records;
- compaction records;
- session branch and label structure;
- model and thinking-level changes.

DocAgent owns:

- task and project metadata;
- skill-pack metadata and published snapshots;
- uploaded originals, converted Markdown, assets, and conversion reports;
- workspace layout and file indexes;
- draft version metadata;
- exported artifacts;
- product audit indexes.

DocAgent should store pointers to Pi session files, not a full duplicate of Pi
history. If enterprise audit requires database-backed retention, the database
copy should be explicitly documented as an index or archive of Pi session JSONL,
not the live source of truth.

## Authoring Flow

1. User creates a DocAgent task.
2. DocAgent creates a workspace with `brief.md`, input folders, context folders,
   draft folders, versions, reviews, artifacts, and logs.
3. Runtime host creates a Pi session with `cwd` set to the task workspace.
4. Runtime host injects the DocAgent core prompt, workspace contract, current
   skill-pack guidance, and converted resource indexes.
5. User sends a prompt or runs `/start-outline`.
6. Pi streams assistant, tool, and file activity.
7. DocAgent UI renders normalized event cards and refreshes draft/workspace
   views from file changes.
8. User can steer, follow up, abort, approve, revise locally, checkpoint, or
   export.

## Migration Strategy

### Phase 1: Pi Runtime Spike

Build a minimal Pi runtime host for authoring only.

Scope:

- one task maps to one Pi session;
- Pi session runs in the task workspace;
- prompt, abort, steer, and event stream are exposed;
- DocAgent UI can show assistant text, tool calls, and draft file writes;
- no skill-pack management migration yet.

Success case:

```text
brief -> context files -> outline -> approval -> draft -> revision -> checkpoint
```

### Phase 2: DocAgent Extension

Move document-specific agent capabilities into a DocAgent Pi extension.

Scope:

- workspace contract helpers;
- checkpoint tool;
- checklist tool;
- export request/tool;
- skill-pack resource loading;
- outline approval request.

### Phase 3: Runtime Simplification

Retire OpenHands as a supported runtime path once Pi covers the authoring loop.

Scope:

- remove or archive OpenHands adapter code;
- remove ACP as the authoring timeline source;
- remove Celery runtime worker paths if Pi runtime host owns long-running
  sessions;
- keep conversion/export workers only where they serve document processing.

### Phase 4: Product Shell Slimming

Simplify backend state around Pi session pointers and product read models.

Scope:

- replace runtime session states with derived status from Pi session/event
  state;
- keep database indexes for tasks, skill packs, artifacts, and workspace files;
- use Pi JSONL as the agent session truth source.

## Testing Strategy

Runtime host tests:

- create Pi session for a workspace;
- stream message and tool events;
- abort a running prompt;
- steer while streaming;
- resume from a Pi session file;
- map file writes to workspace invalidation hints.

Extension tests:

- tools reject paths outside the task workspace;
- draft writes respect Markdown-only internal format;
- checkpoint tool creates monotonically increasing versions;
- checklist and export tools write expected workspace artifacts.

Product integration tests:

- authoring loop creates required context files before `draft/draft.md`;
- outline approval continues the same Pi session;
- local draft edit plus checkpoint remains visible to Pi;
- export creates DOCX/PDF artifacts without asking the agent to format Word
  directly.

Regression tests:

- no new OpenHands dependency in authoring runtime;
- center pane does not consume ACP events as its primary source;
- DocAgent product state can be rebuilt from workspace files plus Pi session
  pointer.

## Risks

### Pi API Stability

Pi is still evolving. Use a pinned version and keep the runtime host boundary
small so upgrades are localized.

### Session Truth Split

Duplicating Pi sessions into DocAgent event tables would recreate the current
ACP/projection complexity. The design avoids that by treating DocAgent database
rows as indexes and product metadata.

### Product-Specific UI Needs

Pi events are agent-centric. DocAgent still needs document-centric cards and
preview invalidation. Use a small normalized event mapper at the runtime host
boundary rather than a broad protocol layer.

### Extension Overreach

Putting all product state in a Pi extension would make management workflows hard
to reason about. Keep extensions focused on agent-facing document actions.

## Open Questions

- Should the first runtime host be a Node service using the Pi SDK, or a Python
  subprocess adapter using `pi --mode rpc`?
- Should Pi session JSONL live inside each task workspace under `logs/` or in a
  DocAgent-managed session directory with pointers from tasks?
- Should export tools call the DocAgent shell API or write export request files
  that a product worker consumes?
- Should the old ACP event table be archived immediately after the Pi spike, or
  kept for a short compatibility window?

## Recommendation

Start with a Node Pi runtime host using the Pi SDK.

This follows the pattern used by Pi-based shells such as OpenPi: keep Pi as the
agent semantic owner and keep the surrounding app responsible for product
authority and UI. It also avoids the heaviest current DocAgent problem: a custom
agent runtime protocol wrapped around a runtime that was not designed to be a
light document authoring core.
