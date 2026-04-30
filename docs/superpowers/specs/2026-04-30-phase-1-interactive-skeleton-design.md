# Phase 1 Interactive Skeleton Design

## Purpose

Phase 1 turns the Phase 0 foundation into a minimal interactive product skeleton.

The goal is not to integrate a real agent runtime yet. The goal is to freeze the API, workspace, timeline, and UI contracts around the Claude Code-style document authoring loop so a real runtime can be connected later without reshaping the product.

## Product Outcome

A user can:

1. Open the web app.
2. Inspect the seed PRD document type.
3. Create a task workspace from a free-form brief.
4. Create a session for that task.
5. Send a message in the authoring timeline.
6. See mock agent activity as semantic timeline events.
7. Read and edit the current Markdown draft.
8. See workspace files, draft versions, conversion reports, and artifacts as first-class product surfaces.

## Non-Goals

- Real OpenHands, Claude Code, Codex, or other runtime integration.
- Multi-user permissions.
- Production storage.
- High-fidelity DOCX/PDF export.
- Full upload UI for complex document conversion.
- Workflow designer or document-type-specific fixed flows.
- RAG or semantic retrieval as the default writing path.

## Recommended Approach

Use an API-first vertical slice with a thin UI.

The API owns task/session state, workspace initialization, mock runtime behavior, semantic timeline generation, and Markdown draft persistence. The web app consumes these APIs without inventing its own product model. The mock runtime adapter produces deterministic events and file writes that exercise the same adapter boundary expected from a future real runtime.

This keeps Phase 1 small while protecting the most important system shape: free-form human-agent interaction over a Markdown workspace.

## Architecture

```text
apps/web
  -> services/api HTTP API
    -> packages/contracts
    -> packages/workspace
    -> packages/timeline
    -> tools/import where needed
    -> agent/runtime-adapters/mock
```

The UI does not read repository files directly. It calls API endpoints.

The API does not decide document writing strategy. In Phase 1, mock runtime behavior is deterministic and clearly marked as a stand-in.

The runtime adapter does not expose raw runtime payloads to the UI. It emits raw events into the backend boundary, which are mapped into semantic timeline events before display.

## Backend Surface

Phase 1 should add a FastAPI service under `services/api`.

Required endpoints:

```text
GET  /health
GET  /doc-types
GET  /doc-types/{doc_type_id}
POST /tasks
GET  /tasks/{task_id}
GET  /tasks/{task_id}/workspace
GET  /tasks/{task_id}/draft
PUT  /tasks/{task_id}/draft
POST /tasks/{task_id}/sessions
GET  /sessions/{session_id}
POST /sessions/{session_id}/messages
GET  /sessions/{session_id}/timeline
```

The service may use local filesystem JSON state for Phase 1. Production database selection is intentionally deferred.

## Workspace Rules

Task workspace creation must use `packages/workspace`.

The API creates:

```text
brief.md
inputs/original/
inputs/markdown/
inputs/assets/
inputs/reports/
context/
draft/
versions/
reviews/
artifacts/
logs/
```

Before any mock draft write, the runtime adapter must create the same required context files expected from a real agent:

- `context/user_intent.md`
- `context/style_notes.md`
- `context/structure_notes.md`
- `draft/outline.md`

The current draft remains `draft/draft.md`.

## Markdown-Only Rule

The agent-facing path remains Markdown-only.

The mock runtime adapter may read:

- `brief.md`
- `inputs/markdown/`
- `doc-types/{doc_type}/SKILL.md`
- `doc-types/{doc_type}/examples/markdown/`
- `doc-types/{doc_type}/examples/reports/`
- `doc-types/{doc_type}/specs/markdown/`
- `doc-types/{doc_type}/specs/reports/`
- `doc-types/{doc_type}/checklists/`

It must not use `inputs/original/`, `examples/original/`, or `specs/original/` as normal drafting input. Original files are audit and re-conversion sources only.

## Mock Runtime Adapter

The mock adapter exists to exercise the product contract, not to impersonate an LLM.

On first user message in a session, it should:

1. Append a user message event.
2. Create context files.
3. Create an outline.
4. Create a simple draft.
5. Emit semantic timeline events for reading skill guidance, extracting style, extracting structure, generating outline, and updating draft.

On later messages, it should:

1. Checkpoint the current draft.
2. Append a short revision note to the draft or replace the selected section when selection support exists.
3. Emit checkpoint and update-draft timeline events.

The adapter should be replaceable behind the documented runtime adapter boundary:

```text
create_session(task_id, workspace_config)
send_message(session_id, message)
stream_events(session_id)
pause(session_id)
resume(session_id)
cancel(session_id)
approve_action(session_id, action_id)
reject_action(session_id, action_id)
get_state(session_id)
```

Phase 1 only needs to implement `create_session`, `send_message`, and state/timeline retrieval.

## UI Surface

Phase 1 should create a minimal React web app under `apps/web`.

Required pages:

```text
/management
/workbench
```

The management page should show:

- document type list
- selected document type details
- resource groups for examples, specs, checklists, export references
- conversion reports and warnings when present
- a visible `SKILL.md` preview
- a Skill Creator chat placeholder

The workbench page should use the planned three-column layout:

```text
Left rail              Center timeline              Right preview/editor
---------              ----------------              --------------------
DocType selector       User messages                 Markdown preview
Task/session list      Agent/tool events             Markdown source editor
Workspace tree         Checkpoints                   Export buttons
Inputs/resources       Checklist/export events       Manual save
Versions/artifacts
```

The first usable path should be:

1. Select PRD.
2. Enter a brief.
3. Create task.
4. Create session.
5. Send a timeline message.
6. See mock agent events.
7. Edit Markdown draft and save.

## UI Design Constraints

- Operational dashboard, not a marketing page.
- No fixed workflow wizard.
- Three-column authoring layout is the primary experience.
- Workspace files are visible because they are part of trust and audit.
- Conversion warnings are visible before resources are used.
- The UI displays semantic timeline events by default.
- The UI may include raw-event access later, but not in Phase 1.

## State Model

Phase 1 state can be local and file-backed.

Suggested state root:

```text
.local/docagent/
  tasks.json
  sessions.json
  timelines/
  workspaces/
```

The repository should ignore `.local/`.

The state shape should align with `packages/contracts`.

## Testing

Backend tests should cover:

- health endpoint
- listing doc types
- creating a task writes the workspace layout
- creating a session stores session state
- sending a message writes context, outline, draft, and timeline events
- draft read/update roundtrip

UI tests can be light in Phase 1:

- component or smoke tests for rendering management and workbench pages
- one API client test or mocked interaction test for the happy path

CI should run:

- existing Phase 0 Python tests
- new API tests
- web lint/test/build once the frontend toolchain is introduced

## Acceptance Criteria

- A fresh developer can run API tests locally.
- A fresh developer can start the API service.
- A fresh developer can start the web app.
- The happy path works with the mock runtime adapter.
- The mock agent reads only Markdown-facing resource paths.
- Timeline events are semantic and use shared contract names.
- Draft Markdown persists through API calls.
- CI covers the new backend and frontend skeleton.

## Open Decisions Deferred

- Real runtime choice: OpenHands, a Codex-like local adapter, direct Responses API tool loop, or another agent server.
- Database choice.
- Auth and permissions.
- Real upload and complex conversion UX.
- High-fidelity export.
- Live streaming transport: SSE, WebSocket, or polling.
