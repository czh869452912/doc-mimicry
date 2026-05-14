# Event Model

The durable interaction record is the ACP event log. The center timeline reads
ACP events and renders native agent activity directly. Semantic DocAgent events
remain as projections for product cards, workspace invalidation, reporting, and
compatibility endpoints.

## ACP Events

ACP events come from the backend session gateway or an ACP-capable runtime
adapter. They may include:

- user message
- agent message
- tool call started
- tool call completed
- tool call failed
- file changed
- approval requested
- session paused
- session resumed

The API exposes the log through `GET /sessions/{session_id}/events` and
`GET /sessions/{session_id}/events/stream`. New runtime work should emit ACP
updates first. Unsupported runtime payloads should be preserved in the ACP
payload instead of being compressed into a semantic summary.

## Semantic Projections

Semantic events are derived from raw event type, path, command, and workspace role.

Examples:

| Raw Signal | Semantic Event |
|---|---|
| read `doc-types/prd/SKILL.md` | Read PRD skill |
| read `doc-types/prd/examples/*` | Analyze best-practice examples |
| write `context/style_notes.md` | Extract style notes |
| write `context/structure_notes.md` | Extract structure notes |
| write `draft/outline.md` | Generate outline |
| write `draft/draft.md` | Update draft |
| run `checkpoint.py` | Create checkpoint |
| write `reviews/checklist_result.md` | Run checklist |
| run `export_docx.py` | Export DOCX |

## Storage

Store all three layers with clear ownership:

- ACP event payload for the canonical timeline and stream resume
- raw runtime payload for audit and debugging when a runtime shim receives one
- semantic projection for DocAgent cards, workspace invalidation, and reporting

The legacy `/timeline` endpoint may continue to return semantic projections for
older clients, but it is not the source of truth for the authoring timeline.

