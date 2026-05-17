# Workspace Contract

The workspace is the agent's durable working memory for one task.

## Layout

```text
/workspace/{task_id}/
  brief.md
  inputs/
    original/
    markdown/
    assets/
    reports/
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
User-created checkpoints use the same version sequence as agent-created checkpoints:
`versions/v001.md`, `versions/v002.md`, and so on. The API creates these
checkpoints from the server-authoritative `draft/draft.md`, records a
`create_checkpoint` timeline/ACP projection when a session exists, and the
workspace tree must expose the generated `versions/*.md` files.

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
    original/
    markdown/
    assets/
    reports/
  specs/
    original/
    markdown/
    assets/
    reports/
  checklists/
  export-references/
```

The agent may read these files but must not modify them.

Agents should read converted Markdown resources, not original binary files. Original files are retained for audit and re-conversion.

## Writing Rules

- Current working draft is `draft/draft.md`.
- Current outline is `draft/outline.md`.
- Draft checkpoints go in `versions/`.
- Checklist results go in `reviews/checklist_result.md`.
- Exported files go in `artifacts/`.
- Logs and agent notes go in `logs/`.
- Converted uploaded inputs go in `inputs/markdown/`.
- Conversion reports go in `inputs/reports/`.
