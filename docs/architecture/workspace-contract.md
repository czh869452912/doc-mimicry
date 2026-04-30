# Workspace Contract

The workspace is the agent's durable working memory for one task.

## Layout

```text
/workspace/{task_id}/
  brief.md
  inputs/
  context/
    user_intent.md
    doc_map.md
    style_notes.md
    structure_notes.md
    decision_log.md
    open_questions.md
    draft_summary.md
  draft/
    outline.md
    draft.md
    sections/
  versions/
  reviews/
    checklist_result.md
    self_review.md
  artifacts/
  logs/
    agent_notes.md
```

## Required Before Drafting

Before writing `draft/draft.md`, the agent must create:

- `context/user_intent.md`
- `context/style_notes.md`
- `context/structure_notes.md`
- `draft/outline.md`

## Required During Revision

Before meaningful revisions, the current draft should be checkpointed to `versions/`.

After user direction changes, update:

- `context/decision_log.md`
- `context/open_questions.md` when relevant
- `context/draft_summary.md`
- `context/doc_map.md`

## Read-Only Inputs

Document type assets are mounted read-only:

```text
/doc-types/{doc_type}/
  SKILL.md
  examples/
  specs/
  checklists/
  export-references/
```

The agent may read these files but must not modify them.

## Writing Rules

- Current working draft is `draft/draft.md`.
- Current outline is `draft/outline.md`.
- Checklist results go in `reviews/checklist_result.md`.
- Exported files go in `artifacts/`.
- Logs and agent notes go in `logs/`.

