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
      -> LiteLLM Model Gateway
```

The runtime host can initially be a Node service colocated with the product
backend. A subprocess RPC adapter remains a fallback for process isolation or a
Python-only deployment, but the preferred implementation is the Pi SDK because
it gives direct typed access to session events and lifecycle controls.

Pi model traffic should continue to route through the product-managed LiteLLM
gateway. The Pi runtime host configures Pi model definitions to target LiteLLM
base URLs and DocAgent model aliases such as `docagent/default`,
`docagent/fast`, and `docagent/reasoning`. This preserves centralized provider
credential handling, model routing, cost tracking, and provider-specific
behavior such as disabling unsupported thinking modes for tool loops.

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

The Shell API should become thinner than the current FastAPI runtime layer. It
keeps product authority around:

- task and skill-pack records;
- file import and conversion;
- workspace file index;
- draft and artifact metadata;
- export routes;
- user-facing audit queries.
- authenticated browser-facing event streams;
- task ownership, authorization, and rate-limit checks before runtime access;
- real-time audit indexing and workspace invalidation notifications.

It should stop owning agent state transitions such as `running_context`,
`await_outline_approval`, and `running_draft` as the core runtime truth. Those
states can remain as derived UI status labels.

### Pi Runtime Host

The runtime host creates and manages Pi sessions for DocAgent tasks.

Responsibilities:

- create or resume a Pi session for a task workspace;
- configure Pi `cwd` to the task workspace;
- configure Pi model definitions to use the LiteLLM gateway and DocAgent model
  aliases;
- inject DocAgent system prompt, current skill pack, and workspace contract;
- register DocAgent tools and extension commands;
- normalize Pi events into a versioned DocAgent UI event stream before handing
  them to the Shell API;
- stream normalized events to the Shell API, which is the only browser-facing
  gateway;
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
- write export request files such as `artifacts/export_request.json` for the
  product shell or file watcher to process;
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

The first implementation should store the Pi session JSONL inside the task
workspace under `logs/session.jsonl`. This keeps task workspaces portable and
consistent with the existing workspace contract. DocAgent records the path in
task/session metadata for lookup.

For audit and tamper resistance, the Shell API should append normalized session
events to an active audit index as they are produced, then export completed
task bundles to immutable long-term storage. The active Pi JSONL remains the
live runtime truth; the archive tiers are compliance and recovery records.

Use a hybrid archive by default:

- `audit_events` database table for active and recent tasks, indexed by task,
  session, event kind, actor, path, and time for in-app audit dashboards,
  search, and administrator reports;
- WORM-capable object storage for completed or retained tasks, storing
  compressed session JSONL exports and audit bundles with object lock or
  equivalent retention controls.

The database tier is an operational index. The object storage tier is the
long-term compliance archive. Neither tier replaces the active Pi session JSONL
as runtime truth.

## Normalized Event Contract

The browser should not consume raw Pi SDK events directly. Pi events are
agent-centric and may change as Pi evolves. The Pi runtime host should publish a
small, versioned DocAgent event contract.

Initial shape:

```yaml
schema_version: 1
id: string
session_id: string
sequence: number
kind:
  user_message
  assistant_delta
  assistant_message
  tool_start
  tool_update
  tool_end
  file_read
  file_write
  approval_request
  approval_response
  status
  error
role: user | assistant | tool | system
status: pending | running | succeeded | failed | cancelled
text: string | null
tool:
  id: string | null
  name: string | null
paths: string[]
projection:
  card_kind: outline | checkpoint | checklist | artifact | null
  summary: string | null
created_at: IsoDateTime
raw_ref:
  pi_session_path: string
  pi_entry_id: string | null
```

The UI may render product cards from `projection.card_kind`, but the event list
itself remains the center-pane source. Raw Pi payloads should stay behind
debug/audit affordances rather than becoming a frontend dependency.

The browser receives this stream through the Shell API. The Shell API verifies
task access, proxies normalized runtime events, writes `audit_events` rows, and
emits workspace invalidation hints before forwarding events to subscribed UI
clients.

## Draft Branches And Variations

Expose Pi session trees as document-facing draft branches or draft variations,
not as raw runtime branches. Users should see content-oriented labels such as
`Detailed Technical Brief` or `Executive Summary`, while Pi branch identifiers
remain runtime metadata.

Initial UI affordance:

- the left rail may show a compact Draft Branches list or tree alongside draft
  versions;
- the right preview/editor may show branch comparison and diff views;
- the center timeline records branch creation, branch switch, and branch merge
  events as normalized DocAgent events.

Switching or forking a draft branch goes through the Shell API:

1. Shell API verifies task ownership and records the user intent.
2. Shell API asks the Pi Runtime Host to switch to or fork the corresponding Pi
   session branch.
3. Shell API checkpoints the current `draft/draft.md` when needed.
4. A product-owned projection step materializes the selected branch's active
   outline and draft back into `draft/outline.md` and `draft/draft.md`, then
   refreshes workspace indexes and preview state.

Do not checkout or rewrite the whole task workspace as an implicit side effect
of branch switching. Only branch-owned draft artifacts should be projected into
the current `draft/` files. Any durable branch snapshot directory, such as a
future `versions/branches/{branch_id}/`, must be added through an explicit
workspace-contract update before implementation.

## Authoring Flow

1. User creates a DocAgent task.
2. DocAgent creates a workspace with `brief.md`, input folders, context folders,
   draft folders, versions, reviews, artifacts, and logs.
3. Runtime host creates a Pi session with `cwd` set to the task workspace and
   session persistence set to `logs/session.jsonl`.
4. Runtime host injects the DocAgent core prompt, workspace contract, current
   skill-pack guidance, and converted resource indexes.
5. User sends a prompt or runs `/start-outline`.
6. Pi streams assistant, tool, and file activity through the runtime host.
7. The runtime host publishes normalized DocAgent events to the Shell API.
8. The Shell API verifies access, writes active `audit_events`, emits workspace
   invalidation hints, and forwards the normalized stream to subscribed UI
   clients.
9. DocAgent UI renders normalized event cards and refreshes draft/workspace
   views from file changes.
10. User can steer, follow up, abort, approve, revise locally, checkpoint, or
   export.

## Migration Strategy

### Phase 1: Pi Runtime Spike

Build a minimal Pi runtime host for authoring only.

Scope:

- one task maps to one Pi session;
- Pi session runs in the task workspace;
- Pi session JSONL lives at `logs/session.jsonl`;
- Pi model traffic routes through LiteLLM aliases;
- Pi events are normalized into the versioned DocAgent event contract;
- prompt, abort, steer, and event stream are exposed through the Shell API;
- active events are indexed into the `audit_events` database table;
- DocAgent UI can show assistant text, tool calls, and draft file writes;
- no skill-pack management migration yet.

Success case:

```text
brief -> context files -> outline -> approval -> draft -> revision -> checkpoint
```

Additional validation:

- local test CLI can prompt, steer, abort, and resume the Pi session;
- normalized event stream is stable without raw Pi SDK event coupling;
- Shell API can proxy the normalized stream without exposing the Node runtime
  host to the browser;
- audit archive receives append-only session records in the active database
  tier.

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
- archive ACP as an authoring timeline source immediately after the Phase 1 Pi
  spike is validated;
- remove Celery runtime worker paths if Pi runtime host owns long-running
  sessions;
- keep conversion/export workers only where they serve document processing.

### Phase 4: Product Shell Slimming

Simplify backend state around Pi session pointers and product read models.

Scope:

- replace runtime session states with derived status from Pi session/event
  state;
- keep database indexes for tasks, skill packs, artifacts, and workspace files;
- keep `audit_events` as the active audit index;
- export completed-task session bundles to WORM-capable object storage;
- use Pi JSONL as the agent session truth source.

## Testing Strategy

Runtime host tests:

- create Pi session for a workspace;
- configure Pi models through LiteLLM aliases;
- stream message and tool events to the Shell API;
- abort a running prompt;
- steer while streaming;
- resume from a Pi session file;
- include stable event metadata needed by the Shell API audit writer;
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
- export request file triggers product-owned DOCX/PDF export;
- Shell API enforces task ownership before proxying runtime streams or commands;
- Shell API forwards normalized events and writes active audit rows;
- draft branch fork/switch checkpoints current draft and projects only selected
  branch draft files into `draft/`;
- export creates DOCX/PDF artifacts without asking the agent to format Word
  directly.

Regression tests:

- no new OpenHands dependency in authoring runtime;
- center pane does not consume ACP events as its primary source;
- center pane does not consume raw Pi SDK events as its primary source;
- browser does not connect directly to the Node Pi Runtime Host;
- branch UI does not expose raw Pi branch identifiers as primary labels;
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

The exception is immutable audit archival. Audit records may mirror Pi JSONL
entries for compliance and tamper resistance, but product code should treat
that archive as read-only history, not the live session state.

### Shell API Stream Bottleneck

Routing runtime streams through FastAPI keeps a single browser-facing gateway,
but it can become a throughput bottleneck. Keep the Shell API proxy thin,
streaming, and backpressure-aware. Do not make it parse raw Pi payloads or own
agent state transitions.

### Product-Specific UI Needs

Pi events are agent-centric. DocAgent still needs document-centric cards and
preview invalidation. Use a small normalized event mapper at the runtime host
boundary rather than a broad protocol layer.

### Branch Projection Drift

Draft branches can confuse users if the Pi session branch, product draft
metadata, and current `draft/` files diverge. Branch switch and fork commands
must be Shell API-mediated, checkpoint the current draft when needed, and emit
explicit normalized events for UI reconciliation.

### Model Gateway Drift

Allowing Pi to talk directly to providers would bypass DocAgent's current model
gateway decision. The runtime host must configure Pi to use LiteLLM aliases by
default and tests should fail if the authoring runtime requires direct provider
endpoints.

### Extension Overreach

Putting all product state in a Pi extension would make management workflows hard
to reason about. Keep extensions focused on agent-facing document actions.

## Resolved Design Defaults

- First runtime host: Node service using the Pi SDK.
- Model gateway: Pi talks to LiteLLM aliases, not direct provider endpoints.
- Pi session location: task workspace `logs/session.jsonl`.
- Browser event source: versioned DocAgent-normalized Pi event stream proxied
  through the Shell API.
- Export tool behavior: write workspace export request files for product-owned
  workers to consume.
- Audit: write active/recent events to `audit_events`, export completed-task
  bundles to WORM-capable object storage, and keep Pi JSONL as the live runtime
  truth.
- Session branches: expose Pi session trees as Draft Branches or Draft
  Variations, with Shell API-mediated fork/switch commands and controlled
  projection into current `draft/` files.
- ACP retirement: archive ACP as an authoring timeline source immediately after
  the Phase 1 Pi runtime spike is validated.

## Implementation Follow-Ups

- Define the `audit_events` schema and completed-task WORM bundle format.
- Add a workspace-contract extension before introducing any durable branch
  snapshot directory outside the current `draft/` and `versions/` rules.
- Decide whether the Draft Branches switcher lives primarily in the left rail,
  the right preview/editor, or both.

## Recommendation

Start with a Node Pi runtime host using the Pi SDK.

This follows the pattern used by Pi-based shells such as OpenPi: keep Pi as the
agent semantic owner and keep the surrounding app responsible for product
authority and UI. It also avoids the heaviest current DocAgent problem: a custom
agent runtime protocol wrapped around a runtime that was not designed to be a
light document authoring core.

The Phase 1 plan should begin by defining the normalized event schema, building
the thin Node runtime host against LiteLLM-backed Pi model definitions, and
validating prompt, steer, abort, and resume through a local test CLI before
touching broader product workflows.
