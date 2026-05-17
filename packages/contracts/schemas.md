# Minimal Shared Schemas

These schemas are the first source of truth for UI, API, tools, and ACP runtime adapters until generated TypeScript/Pydantic models exist.

Field names should stay stable unless a decision record explains the change.

## Common Types

```text
Id = string
IsoDateTime = string
RelativePath = string
```

Paths are workspace-relative unless explicitly documented as repository paths.

## WorkspaceLayout

```yaml
task_id: string
root: string
brief_path: brief.md
inputs:
  original_dir: inputs/original
  markdown_dir: inputs/markdown
  assets_dir: inputs/assets
  reports_dir: inputs/reports
context:
  user_intent: context/user_intent.md
  doc_map: context/doc_map.md
  style_notes: context/style_notes.md
  structure_notes: context/structure_notes.md
  decision_log: context/decision_log.md
  open_questions: context/open_questions.md
  draft_summary: context/draft_summary.md
draft:
  outline: draft/outline.md
  current: draft/draft.md
  sections_dir: draft/sections
versions_dir: versions
reviews:
  checklist_result: reviews/checklist_result.md
  self_review: reviews/self_review.md
artifacts_dir: artifacts
logs:
  agent_notes: logs/agent_notes.md
```

## ImportedResource

```yaml
id: string
scope: task_input | doctype_example | doctype_spec | doctype_checklist | export_reference
owner_id: string
source_path: string
markdown_path: string | null
asset_dir: string | null
conversion_report_path: string | null
mime_type: string
original_filename: string
status: pending | converting | converted | failed | accepted | rejected
created_at: IsoDateTime
updated_at: IsoDateTime
```

Rules:

- `source_path` points to the original upload.
- `markdown_path` points to converted Markdown when conversion succeeds.
- Agent-facing examples/specs/inputs should use `markdown_path`, not `source_path`.

## ConversionReport

```yaml
source_path: string
markdown_path: string | null
asset_dir: string | null
engine: docling | markitdown | pandoc | mineru | marker | pypdf | manual | unknown
status: succeeded | succeeded_with_warnings | failed
warnings:
  - type: string
    message: string
    location: string | null
features_detected:
  tables: number
  images: number
  formulas: number
  footnotes: number
  pages: number | null
created_at: IsoDateTime
```

## AcpEventEnvelope

Canonical session event stored by the backend and streamed to the center
timeline.

```yaml
id: string
session_id: string
sequence: number
event_type: string
payload: object
projection: object
created_at: IsoDateTime
```

Rules:

- `payload` preserves the ACP event or shimmed runtime update.
- `projection` contains optional DocAgent read-model metadata.
- Consumers that need the authoring timeline should read ACP events, not
  semantic projections.

## SemanticTimelineEvent

Derived DocAgent read model for cards, invalidation, and reports.
It is not the authoring timeline contract.

```yaml
id: string
session_id: string
task_id: string
actor: user | agent | tool | system
kind:
  user_message
  agent_message
  read_skill
  analyze_examples
  extract_style
  extract_structure
  generate_outline
  update_draft
  create_checkpoint
  run_checklist
  export_docx
  export_pdf
  approval_requested
  approval_resolved
  error
raw_event_id: string | null
summary: string
paths: string[]
status: pending | running | succeeded | failed | skipped
created_at: IsoDateTime
```

## DraftVersion

```yaml
id: string
task_id: string
version: string
source_path: draft/draft.md
version_path: string
summary: string
created_by: user | agent | system
created_at: IsoDateTime
```

Rules:

- Version paths live under `versions/`.
- Version names should be monotonically increasing, for example `v001.md`.

## Artifact

```yaml
id: string
task_id: string
draft_version_id: string | null
kind: markdown | docx | pdf
path: string
status: pending | created | failed
created_at: IsoDateTime
```

