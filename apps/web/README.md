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

## External ACP UI

The center agent pane can be delegated to an existing ACP client UI instead of
DocAgent's local fallback renderer:

```powershell
powershell -ExecutionPolicy Bypass -File ..\..\tools\acp_ui\prepare_acp_ui.ps1 -Install
Push-Location ..\..\.local\reference\acp-ui
npm run dev:web -- --host 127.0.0.1 --port 4173
Pop-Location

$env:VITE_ACP_UI_URL = "http://127.0.0.1:4173/"
npm run dev
```

Serve the ACP UI locally or from the same deployment origin when possible. The
embed passes `docagentSessionId`, `docagentTaskId`, `docagentWorkspaceRoot`,
`docagentApiBase`, and the `docagentAcpWsUrl` query parameter for
`/sessions/{session_id}/acp/ws`. Unset
`VITE_ACP_UI_URL` to return to the built-in fallback surface.

`tools/acp_ui/prepare_acp_ui.ps1` keeps the third-party UI out of this repo: it
clones `formulahendry/acp-ui` into ignored `.local/reference/acp-ui` and applies
the small DocAgent bootstrap patch that reads the iframe query parameters,
registers a websocket `DocAgent` agent, and opens the session automatically.
