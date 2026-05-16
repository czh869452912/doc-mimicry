# Repo Alignment And Agent Readability Audit

Date: 2026-05-16

Scope: repository organization, current architecture docs, active plans/reviews,
and top-level implementation signals. This is a current-truth audit, not a
historical review of old assistant-ui or JSON-state phases.

## Summary

The product direction remains coherent: DocAgent Workbench is still a
document-version Claude Code workbench, not a fixed workflow builder, template
generator, or RAG-first writing app. The codebase has advanced to an ACP-first
interaction plane with `mock-acp` / `openhands-acp` runtime names, backend-owned
ACP event storage, a local ACP authoring surface, and LiteLLM as the model
gateway for provider-backed runtime traffic.

The largest repo hygiene issue was not architecture drift in the code; it was
stale organization signals. Completed reviews and an already completed ACP UI
embed plan were still in active directories, while the top-level README still
framed the implementation as Phase 0. That makes fresh agents spend attention
on old facts before finding the live product boundary.

## Changes Made In This Pass

- Moved completed or historical reviews from `docs/reviews/active/` to
  `docs/reviews/completed/`.
- Moved the completed external ACP UI embed plan from
  `docs/superpowers/plans/` to `docs/superpowers/completed/`.
- Added a status note to the remaining ACP-native thin client plan because many
  tasks appear already implemented even though checklist boxes remain unchecked.
- Updated the README and docs index so current agents see ACP-first behavior as
  the implementation state, while Phase 0 remains historical context.
- Updated agent-readability guidance with active/completed hygiene rules.
- Narrowed the `workspace/` ignore rule to `/workspace/` so future files under
  `packages/workspace/` are not accidentally hidden from git.
- Removed local ignored `__pycache__` directories that polluted file discovery.

## Current Active Work Signals

- `docs/superpowers/plans/2026-05-15-acp-native-thin-client.md` remains active,
  and now includes a 2026-05-16 reconciliation table. The live code already
  includes ACP helpers, an ACP interaction surface, external ACP UI embed
  support, canonical ACP runtime names, and guard tests around the authoring
  event source.
- `docs/reviews/active/` now contains only this current audit.
- `docs/exec-plans/active/` contains no active durable execution plan.

## ACP-Native Plan Reconciliation

The first reconciliation pass found Tasks 1-6 and 8-11 implemented, Task 7
mostly implemented with `/timeline` retained as compatibility/read-model
output, and Task 12 still open because the full verification bundle has not
been rerun in this pass.

The remaining product/architecture decision is whether to remove the legacy
runtime compatibility layer now or split it into a follow-up plan. The backend
still keeps `LegacyRuntimeAdapter` compatibility plus `_adapter_prompt_operation`
fallback dispatch across legacy document action routes, even though ACP
prompt/events are now the primary authoring path.

## Findings

### Medium: ACP-native plan still needs completion disposition

The active ACP-native thin client plan now has a live-code reconciliation table,
but it remains in `docs/superpowers/plans/` until full verification is rerun and
the legacy compatibility decision is made. This is safer than leaving stale
unchecked tasks unqualified, but it is not yet a completed-plan state.

Suggested action: run the full verification bundle listed in Task 12, then move
the plan to `docs/superpowers/completed/` or replace it with a small legacy
compatibility cleanup plan.

### Medium: Skill-pack management remains under-specified relative to product intent

The docs consistently say management and authoring are separate surfaces, but
current implementation signals still center on the authoring workbench. The
management surface, Skill Creator workflow, document type versioning, and pack
publish contract are not yet represented as a durable product model.

Suggested action: write a focused execution plan for skill-pack versioning and
management UI before adding more document types.

### Medium: Import/export pipeline is still narrower than the Markdown pipeline contract

The current contract says imports normalize DOCX/PDF/PPTX/images/HTML/text into
Markdown plus assets and conversion reports, then export Markdown to DOCX/PDF.
The implemented import tools currently cover text/Markdown normalization and
reporting; export remains planned. This is acceptable for the current stage but
should stay visible as a product gap.

Suggested action: keep `docs/architecture/markdown-pipeline.md` as the contract,
but open an implementation plan for binary import, conversion warning display,
and first DOCX export.

### Low: Generated file discovery can mislead orientation

Ignored `__pycache__` directories had appeared under `packages/workspace/`.
They were untracked, but `rg --files` still surfaced them because ignored files
can be visible depending on command options and local state.

Suggested action: keep generated artifacts out of source directories and run
the documentation-only structure check before claiming cleanup complete.

### Low: Root ignore rules should avoid package-name collisions

The previous `workspace/` ignore rule also matched nested paths such as
`packages/workspace/new-helper.py`. Existing tracked files were safe, but future
new helpers under that package could be silently ignored.

Suggested action: keep top-level generated directory ignores root anchored,
such as `/workspace/`.

## Verification Added Or Updated

Documentation-only or organization-only changes in this pass should be checked
with:

```powershell
Get-ChildItem -Recurse -File | Select-Object FullName
```

For the remaining ACP-native plan reconciliation, use its own focused frontend,
backend, and compose verification commands after each concrete code task.
