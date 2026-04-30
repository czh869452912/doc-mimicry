# Web App

React document workbench UI.

Owns:

- Management dashboard for document type packs.
- Resource upload, conversion review, and Skill Creator surface.
- Chat and user interrupt controls.
- Agent timeline.
- Draft preview and diff.
- Version and artifact views.
- Approval UI.

Does not own:

- Agent writing logic.
- Workspace contract enforcement.
- Runtime-specific event payload interpretation beyond shared contracts.

## Main Surfaces

- Management: document type resources, converted Markdown, `SKILL.md`, checklists, publish/version.
- Authoring: three-column document type/project/session workspace, timeline, Markdown preview/editor, export.
