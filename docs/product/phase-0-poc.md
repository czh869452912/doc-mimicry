# Phase 0 PoC

## Goal

Validate the document-version Claude Code experience with one document type and one task workspace.

## In Scope

- PRD document type pack.
- User brief as text.
- Optional uploaded input materials represented as Markdown or plain text.
- Best-practice examples, specs, and checklist as readable files.
- Agent-generated context files.
- Outline, draft, checkpoint, local revision, checklist, DOCX export.
- Semantic timeline mapping from raw agent events.

## Out Of Scope

- RAG.
- Multiple document types in the UI.
- Full user/team permission model.
- High-fidelity Word layout.
- Workflow designer.
- Complex approval chains.

## Happy Path

1. User creates a PRD task.
2. Backend initializes workspace and mounts PRD skill pack.
3. Agent reads brief, inputs, skill, examples, specs, and checklist.
4. Agent writes `context/user_intent.md`, `context/style_notes.md`, `context/structure_notes.md`, and `draft/outline.md`.
5. User confirms or changes the plan.
6. Agent writes `draft/draft.md`.
7. User asks for a local revision.
8. Agent checkpoints and edits only the relevant section.
9. Agent runs checklist and writes `reviews/checklist_result.md`.
10. User approves export.
11. Agent calls the fixed export script.

## Acceptance Criteria

- User can interrupt and redirect without starting a new task.
- Agent maintains context files.
- Agent imitates structure and style, not example content.
- A draft version is created before meaningful revision.
- Timeline shows semantic actions, not only low-level file operations.
- DOCX artifact is produced.

