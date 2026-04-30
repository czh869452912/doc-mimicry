# Event Model

The product should expose a semantic timeline while preserving access to raw runtime events.

## Raw Events

Raw events come from the agent runtime and may include:

- user message
- agent message
- tool call started
- tool call completed
- tool call failed
- file changed
- approval requested
- session paused
- session resumed

## Semantic Events

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

Store both:

- raw event payload for audit and debugging
- semantic event for timeline UI

