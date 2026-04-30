# Phase 2 Authoring Loop

## Version Name

V0.2 / Phase 2: single document type authoring loop.

## Goal

Phase 2 turns the Phase 1 interactive skeleton into a usable PRD authoring loop.

The version goal is:

> A user can start from a brief and Markdown-facing input materials, collaborate with the agent loop, and produce a checkable, revisable, exportable PRD draft.

Phase 2 is not a UI patch round. Every visible control should correspond to a real API action, workspace file, timeline event, or artifact.

## Product Promise

By the end of Phase 2, DocAgent Workbench should demonstrate the core product promise with one document type:

1. The user brings intent and materials.
2. The system preserves those materials in an inspectable workspace.
3. The agent loop creates durable context files.
4. The user reviews the outline before drafting.
5. The draft can be revised through selected text and conversation.
6. Meaningful revisions create checkpoints.
7. Checklist review and export produce workspace artifacts.
8. The timeline explains what happened in semantic product language.

## Primary Demo Path

The version is accepted only if this path works end to end:

```text
Enter a product idea
  -> upload or paste input material
  -> convert material to Markdown
  -> create task and session
  -> build context files
  -> propose outline
  -> user approves or edits outline
  -> generate PRD draft
  -> user selects a passage and requests revision
  -> checkpoint current draft
  -> revise selected passage
  -> run checklist
  -> export Markdown artifact
```

Low-fidelity DOCX export may be added if it does not distract from the loop, but Markdown artifact export is enough for Phase 2 acceptance.

## Recommended Approach

Build a real local authoring loop before integrating a fully general external runtime.

The Phase 1 mock runtime should evolve into a controlled document-agent loop with explicit states. It should still sit behind the runtime adapter boundary so it can later be replaced by OpenHands, a Codex-like adapter, or a Responses API tool loop.

This avoids two traps:

- continuing to add empty UI surfaces;
- binding the product too early to one runtime before the workspace, event, and human-in-the-loop contracts are strong.

## Core Loop States

The Phase 2 runtime adapter should expose a state machine with these semantic steps:

```text
analyze_inputs
build_context
propose_outline
await_outline_approval
draft_document
revise_selection
run_checklist
export_artifact
```

These states are product states, not document-type-specific workflows. They are the generic shape of a document coding-agent loop.

The PRD document type supplies skill guidance, examples, specs, and checklist criteria. It must not hard-code a separate workflow.

## In Scope

### Workspace Browser

The authoring left rail should display the real task workspace.

Required groups:

- `brief.md`
- `inputs/original`
- `inputs/markdown`
- `inputs/reports`
- `context/*`
- `draft/outline.md`
- `draft/draft.md`
- `versions/*`
- `reviews/*`
- `artifacts/*`

Users should be able to open text and Markdown files from the workspace tree.

### Import Pipeline

Phase 2 should support user materials through API and UI.

Required input formats:

- direct text input
- `.md`
- `.markdown`
- `.txt`

The system should:

- write originals to `inputs/original`;
- write converted Markdown to `inputs/markdown`;
- write conversion reports to `inputs/reports`;
- show conversion status and warnings in the UI.

Complex formats such as DOCX, PDF, images, spreadsheets, and slides remain deferred unless a simple adapter already exists and does not expand scope.

### Authoring Runtime Adapter

The adapter should perform real workspace operations:

- read `brief.md`;
- read `inputs/markdown`;
- read `doc-types/prd/SKILL.md`;
- read `doc-types/prd/examples/markdown` and reports;
- read `doc-types/prd/specs/markdown` and reports;
- read `doc-types/prd/checklists`;
- write `context/user_intent.md`;
- write `context/style_notes.md`;
- write `context/structure_notes.md`;
- write `context/doc_map.md`;
- write `draft/outline.md`;
- write `draft/draft.md`;
- checkpoint before meaningful revision;
- write `reviews/checklist_result.md`;
- write exported artifact files under `artifacts`.

The adapter must not use original binary paths as normal drafting input.

### Human-In-The-Loop Controls

Required user controls:

- create task from selected PRD type;
- add input material;
- start agent loop;
- approve outline;
- edit outline before approval;
- send free-form message;
- select draft passage and request targeted revision;
- manually save draft;
- run checklist;
- export Markdown artifact.

The user should not need to restart a task when changing direction.

### Timeline

The timeline should show semantic events for:

- user messages;
- input conversion;
- context creation;
- outline proposal;
- outline approval;
- draft generation;
- checkpoint creation;
- selected passage revision;
- checklist review;
- artifact export;
- errors.

Raw events may be retained for audit, but the default timeline should remain semantic.

### Management Surface

The management interface should become truthful for the PRD doc type:

- show `SKILL.md`;
- show examples, specs, reports, checklists, and export references by resource group;
- show conversion reports and warnings when present.

Full Skill Creator remains out of scope for Phase 2.

## Out Of Scope

- Multiple editable document type creation flows.
- Full Skill Creator automation.
- RAG as the default writing path.
- Production database selection.
- User/team permissions.
- High-fidelity DOCX/PDF export.
- Native DOCX editing.
- Full OpenHands integration.
- Multi-agent orchestration.

## UI Principles

- Do not add decorative controls without backing API behavior.
- Do not hide workspace files.
- Keep the authoring UI centered on timeline, workspace, and draft.
- Keep the management UI operational and dense.
- Preserve Markdown as the internal editing and agent-facing format.
- Make waiting states, failures, and conversion warnings visible.

## Backend Principles

- API endpoints should expose workspace-backed state, not UI-only fixtures.
- File-backed local state remains acceptable for Phase 2.
- Runtime actions must go through the adapter boundary.
- Timeline events must use shared semantic event names.
- Workspace validation should prevent drafting before required context and outline files exist.

## Acceptance Criteria

Phase 2 is complete when a fresh local developer can:

1. Run `.\start-dev.cmd`.
2. Open the web app.
3. Create a PRD task from a free-form brief.
4. Add at least one Markdown or text input material.
5. Start the authoring loop.
6. Inspect generated context files and outline in the workspace browser.
7. Approve or edit the outline.
8. Generate a PRD draft.
9. Select a passage and request a targeted revision.
10. See a checkpoint under `versions`.
11. Run the checklist and open `reviews/checklist_result.md`.
12. Export a Markdown artifact and see it under `artifacts`.
13. Refresh the browser and recover the task/session state.

Automated verification should cover:

- import conversion for supported formats;
- workspace tree listing and file read endpoints;
- loop state transitions;
- outline approval;
- draft generation;
- selected text revision with checkpoint;
- checklist result creation;
- artifact export;
- timeline semantic events for the demo path;
- frontend build.

## Version Gate

Do not start Phase 3 runtime integration until Phase 2 can demonstrate the full PRD authoring loop without manual file editing.

Phase 3 may then replace the controlled authoring loop with a real runtime adapter while preserving the same workspace, API, timeline, and UI contracts.
