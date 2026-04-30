# Phase 0 PoC

## Goal

Validate the document-version Claude Code experience with one document type and one task workspace.

## In Scope

- PRD document type pack.
- User brief as text.
- Optional uploaded input materials converted to Markdown or plain text.
- Best-practice examples, specs, and checklist converted to readable Markdown/YAML files.
- Agent-generated context files.
- Outline, draft, checkpoint, local revision, checklist, DOCX export.
- Semantic timeline mapping from raw agent events.
- Basic management surface for document type resources and Skill Creator can be mocked or minimal.

## Out Of Scope

- RAG.
- Multiple document types in the UI.
- Full user/team permission model.
- High-fidelity Word layout.
- Workflow designer.
- Complex approval chains.
- Native DOCX editing.

## Happy Path

1. User creates a PRD task.
2. Backend converts uploaded inputs to Markdown when needed.
3. Backend initializes workspace and mounts PRD skill pack.
4. Agent reads brief, converted inputs, skill, examples, specs, and checklist.
5. Agent writes `context/user_intent.md`, `context/style_notes.md`, `context/structure_notes.md`, and `draft/outline.md`.
6. User confirms or changes the plan.
7. Agent writes `draft/draft.md`.
8. User selects a paragraph and asks for a local revision.
9. Agent checkpoints and edits only the relevant section.
10. Agent runs checklist and writes `reviews/checklist_result.md`.
11. User approves export.
12. Agent calls the fixed export script.

## Acceptance Criteria

- User can interrupt and redirect without starting a new task.
- Agent maintains context files.
- Agent imitates structure and style, not example content.
- Inputs and document resources used by the agent are Markdown.
- A draft version is created before meaningful revision.
- Timeline shows semantic actions, not only low-level file operations.
- DOCX artifact is produced.
