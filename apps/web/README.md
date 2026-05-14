# Web App

React document workbench UI.

Owns:

- Management dashboard for document type packs.
- Resource upload, conversion review, and Skill Creator surface.
- Chat and user interrupt controls.
- ACP-backed agent timeline.
- Draft preview and diff.
- Version and artifact views.
- Approval UI.

Does not own:

- Agent writing logic.
- Workspace contract enforcement.
- Runtime-specific event payload interpretation beyond ACP contracts and DocAgent projections.

## Main Surfaces

- Management: document type resources, converted Markdown, `SKILL.md`, checklists, publish/version.
- Authoring: three-column document type/project/session workspace, timeline, Markdown preview/editor, export.

## Phase 1 Local Run

```powershell
npm install
npm run dev
```

The app expects the API at `http://127.0.0.1:8000` unless `VITE_API_BASE` is set.
