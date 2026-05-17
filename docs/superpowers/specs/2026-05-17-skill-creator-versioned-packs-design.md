# Skill Creator Versioned Packs Design

## Status

Proposed for review. This spec captures the accepted direction from the
repo-alignment audit follow-up: implement Skill Creator as a material-driven
agent experience over versioned document type skill packs.

## Reader And Action

Reader: an engineer or agent planning the first product-grade implementation of
Skill Creator and skill-pack versioning.

Post-read action: write an implementation plan that introduces versioned
document type packs, material-driven Skill Creator sessions, and published pack
binding for authoring tasks without turning document types into workflows or
templates.

## Context

The product direction already says DocAgent Workbench should have separate
management and authoring surfaces. The management surface should help users
create document type skill packs from best-practice examples, writing
specifications, checklists, and export references. The authoring surface should
then use a configured pack while preserving the Claude Code / Codex-style loop.

Current implementation is much narrower:

- document types are read from the repository `doc-types` directory;
- `SKILL.md` and resource files are listed read-only;
- the settings drawer has a Skill Creator placeholder;
- authoring tasks bind only to a document type id, not to a published pack
  version;
- there is no draft/published separation for skill-pack changes.

The missing product behavior is not a manual `SKILL.md` editor. Users should
provide materials, then collaborate with a Skill Creator agent that reads those
materials, explains what it learned, drafts the skill guidance, suggests
checklists and notes, and revises the pack through conversation. Direct editing
remains available for human correction, but it is not the primary creation
path.

## Goals

- Treat a document type skill pack as a versioned product object.
- Keep a mutable draft pack separate from immutable published versions.
- Let users upload or paste best-practice examples, specifications, checklists,
  and export references into a pack workspace.
- Convert usable text resources to Markdown and retain conversion reports before
  Skill Creator reads them.
- Add a Skill Creator agent session that can generate and revise `SKILL.md`,
  checklist files, and resource notes from pack materials.
- Let users continue through conversation or direct edits before publishing.
- Bind authoring tasks to a published pack version for reproducibility.
- Keep examples focused on structure, style, organization, and review habits,
  not semantic source retrieval.

## Non-Goals

- Do not build a fixed DAG workflow builder for document types.
- Do not make examples into content templates or semantic RAG sources by
  default.
- Do not require humans to hand-write `SKILL.md` before Skill Creator can help.
- Do not let authoring tasks consume mutable draft pack files.
- Do not require high-fidelity DOCX/PDF import or export in the first
  implementation; unsupported formats may produce conversion reports that mark
  the resource unavailable for generation.
- Do not solve multi-user permissions, approval routing, or marketplace
  distribution in this pass.

## Product Model

### Document Type Pack

A document type pack represents a reusable writing family such as PRD,
proposal, risk report, or policy memo.

Each pack has:

- stable id;
- title and short description;
- draft state;
- published versions;
- resource groups;
- generated or edited skill artifacts;
- validation status.

The pack is not a workflow. It teaches an agent how to write and review a
document family.

### Draft Pack

The draft pack is the editable workspace for management. It can change as users
upload resources, run Skill Creator, chat with the agent, or edit generated
files.

Draft pack changes do not affect existing authoring tasks. A draft becomes
available to authoring only after publish.

### Published Pack Version

A published version is immutable. It contains the exact skill artifacts and
resource metadata that authoring tasks should use.

Version names should be monotonically increasing within a pack, such as
`v001`, `v002`, and `v003`. The product may display a combined label such as
`prd@v003`.

Published versions should record:

- generated skill artifact checksums or revision ids;
- resource ids and conversion report ids used for generation;
- validation results;
- created timestamp;
- human publish note.

### Pack Resources

Resources are grouped by purpose:

- examples: best-practice documents for structure, style, density, and
  organization;
- specs: explicit writing rules, standards, terminology, and constraints;
- checklists: review criteria, quality bars, and acceptance checks;
- export references: style references for future export behavior.

Each resource should retain:

- original filename;
- resource group;
- original source path or storage key;
- converted Markdown path when available;
- conversion report path;
- status such as `ready`, `warning`, `failed`, or `unsupported`;
- short user-facing summary generated or edited by Skill Creator.

Skill Creator reads converted Markdown and conversion reports. It should not
read original binary files as normal context.

### Skill Artifacts

The first implementation should support these editable artifacts:

- `SKILL.md`: concise agent guidance with frontmatter and instructions;
- checklist YAML or Markdown files;
- resource notes explaining what examples/specs/checklists contribute;
- optional publish notes.

Skill artifacts should follow the same broad quality rules as Codex skills:
clear trigger description, concise instructions, progressive disclosure, and no
unnecessary auxiliary files. For document packs, this means the generated
`SKILL.md` should focus on writing behavior and review habits, while detailed
source materials remain in resource files.

## Skill Creator Experience

Skill Creator should feel like using Claude Code or Codex inside the management
surface.

The user can:

- create a pack draft;
- upload or paste materials into resource groups;
- ask Skill Creator to generate the first pack;
- inspect what materials influenced the generated guidance;
- continue the conversation to revise tone, scope, checklist rigor, or
  constraints;
- directly edit generated artifacts when needed;
- run validation;
- publish a new version.

The agent should:

- read converted resource Markdown and conversion reports;
- summarize observed document shape, tone, recurring sections, table/list
  patterns, and review criteria;
- draft or update `SKILL.md`;
- draft or update checklist files;
- keep generation notes traceable to resource ids, not copied source passages;
- warn when resources are failed, unsupported, low-confidence, or too sparse;
- ask focused questions when materials conflict or do not support a usable
  skill.

The agent must not:

- copy source wording into the generated skill;
- invent domain constraints not supported by materials or user instruction;
- encode a fixed workflow for every authoring task;
- hide conversion warnings;
- publish automatically without explicit user action.

## Management Surface

The management surface should be a dense operational dashboard, not a landing
page or wizard.

First-version areas:

- pack list with draft/published status;
- pack detail header with current draft status and latest published version;
- resource groups with upload/paste, conversion status, and warning visibility;
- Skill Creator conversation;
- generated artifact editor/preview;
- validation panel;
- publish/version panel.

The existing settings drawer can remain a short-term entry point, but the
product model should not be constrained to a drawer. If the first UI iteration
uses the drawer, the components should still be structured so a dedicated
management route can reuse them later.

## Authoring Binding

Authoring tasks should bind to a published pack version, not only to a mutable
document type id.

When a task is created, the backend resolves:

- pack id;
- selected or latest published version id;
- skill artifact snapshot;
- resource metadata available to the runtime.

The task should keep that binding even if a newer pack version is published
later. Users may create new tasks with the newer version, but existing tasks do
not silently change behavior.

For compatibility, existing seed packs may be bootstrapped as an initial
published version.

## Backend Boundary

The backend owns pack metadata, draft state, published versions, validation,
resource conversion status, authoring task binding, and audit trails.

Expected backend capabilities:

- list packs and versions;
- create a draft pack;
- read and update draft artifacts;
- add text or uploaded resources to draft resource groups;
- record conversion reports;
- start or continue a Skill Creator session for a draft pack;
- persist Skill Creator events and generated artifact revisions;
- validate draft pack artifacts;
- publish a draft as an immutable version;
- resolve published pack versions for authoring task creation.

Skill Creator can reuse the ACP interaction plane, but it should have a
management-scoped session type or metadata so authoring timeline events and
management generation events do not blur together.

## Runtime Boundary

Skill Creator is an agent loop over a pack workspace, not over a document task
workspace.

The runtime prompt should include:

- pack id and draft workspace root;
- user intent for the pack;
- resource manifest with statuses and conversion reports;
- converted resource Markdown paths;
- current generated artifacts;
- rules forbidding workflows, templates, semantic copying, and hidden binary
  reads;
- expected outputs for `SKILL.md`, checklist files, and notes.

The runtime should write through product-controlled tools or constrained file
paths. The backend should validate generated artifacts before allowing publish.

## Storage Shape

The implementation can choose database tables, filesystem layout, or a hybrid,
but it should preserve these invariants:

- draft pack mutable state is separate from published version immutable state;
- resource originals, converted Markdown, and reports are traceable;
- generated artifact revisions are auditable;
- published authoring inputs are reproducible;
- repository seed packs can still exist as bootstrapping fixtures.

A practical first version may store pack workspaces under product state storage
and keep relational rows for ids, statuses, versions, and bindings.

## Validation

Validation should run before publish and be callable independently.

Minimum validation checks:

- pack id is valid and path-safe;
- `SKILL.md` exists and has valid skill frontmatter;
- skill body is non-empty and concise enough for runtime context;
- skill text does not contain obvious source-copy markers from examples;
- required resource groups are either populated or explicitly acknowledged as
  absent;
- conversion failures are visible and not treated as ready materials;
- checklist files parse if YAML is used;
- published version snapshot can be resolved by task creation.

Validation failures block publish. Warnings can allow publish only when they are
explicitly acknowledged by the user.

## Testing Strategy

Backend tests should cover:

- pack creation and safe id validation;
- resource add/list flows and conversion report persistence;
- Skill Creator session creation with management metadata;
- generated artifact update and direct edit persistence;
- validation pass/fail cases;
- publish immutability;
- authoring task binding to a published version;
- compatibility bootstrap for the seed PRD pack.

Frontend tests should cover:

- management UI lists draft and published pack status;
- resource groups show conversion warnings;
- Skill Creator conversation can request generation and display generated
  artifact updates;
- direct artifact edits are preserved;
- publish is blocked on validation failure;
- authoring task creation uses a published version.

Contract tests should cover the shared response/request shapes used by backend
and frontend.

## Rollout

The safest rollout is staged:

1. Introduce pack/version data model and bootstrap the existing PRD seed pack as
   a published version.
2. Add draft pack resources and generated artifact storage.
3. Add Skill Creator session prompts and backend routes for generation and
   revision.
4. Add management UI for resources, conversation, generated artifacts,
   validation, and publish.
5. Bind authoring tasks to published versions and keep legacy doc-type id
   creation as a compatibility path until migrated.

Each stage should preserve the current authoring loop.

## Open Questions

- Should the first Skill Creator runtime use the same mock ACP adapter as
  authoring, or a narrower deterministic generator until the management loop is
  stable?
- Should direct artifact edits create explicit revision records in the first
  version, or is updated timestamp plus publish snapshot enough for MVP?
- Should published versions be stored as copied files in state storage, database
  rows with JSON payloads, or both?
- Should the first UI live inside the existing settings drawer or introduce a
  dedicated management route immediately?
