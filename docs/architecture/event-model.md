# Event Model

The durable interaction record is the ACP event log. The center timeline reads
ACP events and renders native agent activity directly. Semantic DocAgent events
are projections for product cards, workspace invalidation, reporting, and
derived read endpoints.

This is the only formal event contract for the agent-to-backend-to-UI chain.

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
`GET /sessions/{session_id}/events/stream`. New runtime work emits ACP updates
first. Unsupported runtime payloads are preserved in the ACP payload instead of
being compressed into a semantic summary.

## Semantic Projections

Semantic events are derived from ACP event type, payload, path, command, and
workspace role. They are rebuildable read models, not a second event protocol.

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
| backend export route writes `artifacts/*.docx` | Export DOCX |
| backend export route writes `artifacts/*.pdf` | Export PDF |

## Storage

Store all three layers with clear ownership:

- ACP event payload for the canonical timeline and stream resume
- raw runtime payload for audit and debugging when a runtime shim receives one
- semantic projection for DocAgent cards, workspace invalidation, and reporting

Every product-created semantic event that affects user trust or workspace state
must be persisted through the shared semantic-event helper so it appears in both
the compatibility `/timeline` read model and the ACP event log consumed by the
authoring UI.

The `/timeline` endpoint returns semantic projections as a derived read
endpoint. It is not the source of truth for the authoring timeline.

