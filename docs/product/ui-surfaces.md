# UI Surfaces

DocAgent Workbench has two primary user interfaces:

1. Management interface.
2. Authoring interface.

They share the same product model but serve different jobs.

## Management Interface

The management interface is a dashboard for building and maintaining document type skill packs.

It should help users configure reusable imitation resources without designing fixed workflows.

### Jobs

- Create a document type.
- Upload best-practice documents.
- Upload writing specifications.
- Upload checklists.
- Upload optional export reference files.
- Convert uploaded resources to Markdown.
- Inspect converted Markdown and conversion warnings.
- Use a Skill Creator conversation to generate or revise `SKILL.md`, checklists, and resource notes.
- Publish and version a document type pack.

### Main Areas

```text
DocType Dashboard
  -> DocType list
  -> DocType detail
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
- Summarize observed structure and style.
- Draft `SKILL.md`.
- Suggest checklist items.
- Revise a document type pack after user feedback.

It must not:

- Build a fixed workflow per document type.
- Treat examples as semantic source material by default.
- Turn export reference files into content templates.

## Authoring Interface

The authoring interface is the main document imitation workspace. It should feel closer to Codex App or Claude Code than to a document management system.

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
- Do not hide workspace files; they are part of user trust and audit.
- Do not force users into a wizard or fixed workflow.
- Let users interrupt from the timeline at any time.
- Make conversion warnings visible before a resource is used in a skill pack or task.

