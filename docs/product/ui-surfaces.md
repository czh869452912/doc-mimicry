# UI Surfaces

DocAgent Workbench has two primary user interfaces:

1. Management interface.
2. Authoring interface.

They share the same product model but serve different jobs.

## Management Interface

The management interface is a dashboard for building and maintaining versioned document type skill packs.

It should help users configure reusable imitation resources without designing fixed workflows.

### Jobs

- Create a skill pack.
- Paste or upload best-practice documents.
- Paste or upload writing specifications.
- Paste or upload checklists.
- Paste or upload optional export reference files.
- Convert resources to Markdown at import boundaries.
- Inspect converted Markdown and conversion warnings.
- Use a Skill Creator conversation to generate or revise `SKILL.md`, checklists, and resource notes.
- Validate, publish, and version a skill pack.

### Main Areas

```text
Skill Pack Management
  -> Skill pack list
  -> Skill pack detail
    -> Resources
    -> Converted Markdown
    -> Skill Creator chat
    -> SKILL.md editor/preview
    -> Checklists
    -> Publish/version panel
```

### Resource Types

- Best-practice documents: teach structure, narration, information density, table/list usage, and organization.
- Specifications: teach explicit writing rules and constraints.
- Checklists: define review criteria.
- Export references: optional DOCX/PDF styling references used only during export.

### Skill Creator

Skill Creator should feel like a Claude Code-style interaction over a document type pack.

It can:

- Read uploaded resource Markdown.
- Read current artifacts before revising them.
- Summarize observed structure and style.
- Draft `SKILL.md`.
- Suggest checklist items.
- Revise a document type pack after user feedback.
- Preserve direct user edits as current artifact state.

It must not:

- Build a fixed workflow per document type.
- Treat examples as semantic source material by default.
- Turn export reference files into content templates.

## Authoring Interface

The authoring interface is the main document imitation workspace. It should feel closer to Codex App or Claude Code than to a document management system.

Authoring tasks bind to immutable published skill-pack versions when available.
Legacy repo `doc-types/*/SKILL.md` remains a fallback only for packs that have
not yet been published.

### Layout

Use a three-column layout.

```text
Left rail              Center timeline              Right preview/editor
---------              ----------------              --------------------
DocType selector       User messages                 Markdown preview
Project list           Agent messages                Markdown editor
Session list           Tool events                   Selected paragraph
Workspace tree         Checkpoints                   Export actions
Inputs                 Checklist results             Version/diff view
Draft versions         Export events
Artifacts
```

### Left Rail

The left rail organizes work:

- Select document type.
- Create or select project.
- Create or select session.
- Inspect project workspace:
  - inputs
  - converted Markdown
  - context files
  - draft
  - versions
  - reviews
  - artifacts

### Center Timeline

The center timeline is the ACP-backed interaction spine.

It should show:

- User requests.
- Agent progress.
- File reads/writes as ACP events with DocAgent projections.
- Checkpoints.
- Checklist results.
- Export events.
- Approval prompts when needed.

The timeline consumes the backend-owned ACP event log. It may render semantic
DocAgent cards, but those cards are projections from ACP events. The UI should
not introduce a separate runtime event protocol.

### Right Preview And Editor

The right side shows the current Markdown document.

It should support:

- Markdown preview.
- Source Markdown editing.
- Section or paragraph selection.
- Send selected passage to the timeline as context for revision.
- Manual edits with checkpoint discipline.
- Export buttons for DOCX/PDF.

Phase 0 should prefer a source-oriented Markdown editor plus preview over heavy WYSIWYG editing.

## UI Principles

- Keep the management interface operational and dense.
- Keep the authoring interface focused on the agent loop.
- Keep management and authoring as separate surfaces; the settings drawer may link to management, but the dedicated route is the durable home.
- The settings drawer may summarize runtime and repository document-type details, but the full Skill Pack Management workflow belongs only on `/management/skill-packs`.
- Do not hide workspace files; they are part of user trust and audit.
- Do not force users into a wizard or fixed workflow.
- Let users interrupt from the timeline at any time.
- Make conversion warnings visible before a resource is used in a skill pack or task.

