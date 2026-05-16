# Repo Alignment And Agent Readability Audit

Date: 2026-05-16

Status: Completed and archived on 2026-05-17 after the ACP-native plan
reconciliation and legacy runtime compatibility cleanup were merged to `main`.

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

## Work Signals At Audit Completion

- `docs/superpowers/completed/2026-05-15-acp-native-thin-client.md` is the
  reconciled and verified ACP-native thin client record.
- `docs/superpowers/completed/2026-05-16-legacy-runtime-compatibility-cleanup.md`
  is the ACP follow-up record for removing the legacy runtime document-action
  fallback.
- `docs/reviews/active/` contains no current unresolved audit file after this
  audit was archived.
- `docs/exec-plans/active/` contains no active durable execution plan.

## ACP-Native Plan Reconciliation

The first reconciliation pass found Tasks 1-6 and 8-11 implemented, Task 7
mostly implemented with `/timeline` retained as compatibility/read-model
output, and Task 12 open until verification was rerun.

Task 12 verification was then run on 2026-05-16:

- `npm run test:unit -- --run` in `apps/web`: 25 test files and 117 tests passed.
- `npm run build` in `apps/web`: build passed with only the existing Vite large-chunk warning.
- `python -m pytest packages/contracts/tests packages/timeline/tests services/api/tests agent/runtime-adapters/mock/tests agent/runtime-adapters/openhands/tests tests/test_litellm_compose.py tests/test_dev_entrypoint.py -q --basetemp=.local/pytest-tmp-acp-thin-final`: 208 tests passed.
- `docker compose config`: exited 0 and rendered the expected ACP runtime and LiteLLM configuration.
- Runtime-name guard search for `OPENHANDS_CONTAINER_BASE_URL`, `DOCAGENT_RUNTIME=mock`, and `DOCAGENT_RUNTIME=openhands` in current-truth docs/config returned no matches.

The legacy runtime compatibility layer was then removed in the follow-up:
`RuntimeAdapter` now aliases `AcpRuntimeAdapter`, authoring routes and the ACP
WebSocket require `send_prompt`, and background worker dispatch rejects legacy
operation names.

## Findings

### Resolved: Legacy runtime compatibility cleanup

The ACP-native thin client plan is verified and archived, and the backend no
longer supports route-level legacy document-action fallback dispatch. Product
actions are `send_prompt` calls with metadata; `/timeline` remains a
compatibility/read-model output.

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

For the legacy runtime compatibility cleanup follow-up, use the verification
commands in `docs/superpowers/completed/2026-05-16-legacy-runtime-compatibility-cleanup.md`.
