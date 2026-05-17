# Agent Workbench Alignment Roadmap Implementation Plan

> **For agentic workers:** This is a durable milestone plan. When implementing an individual phase, first create a task-sized plan under `docs/superpowers/plans/` and use `superpowers:executing-plans` or `superpowers:subagent-driven-development`.

**Goal:** Move DocAgent from a working generic authoring MVP into a cleaner document-version Claude Code workbench by hardening real runtime contracts, strengthening the authoring loop, controlling frontend bundle size, and then reducing management UI complexity.

**Architecture:** Preserve the ACP-first runtime boundary, Markdown-only workspace contract, and separation between management and authoring surfaces. Keep document-type specificity in published skill packs, task metadata, and prompt bundles rather than adding fixed workflows, templates, or RAG-first behavior. Land each phase as a separately verifiable vertical slice.

**Tech Stack:** FastAPI, SQLAlchemy state layer, ACP contracts, mock and OpenHands runtime adapters, React, TanStack Query, TanStack Router, Vite, Vitest, Playwright, pytest, Testcontainers Postgres.

---

## Goal

Implement the next alignment pass after the May 17 review:

1. Prove the real OpenHands/ACP path respects generic document-type behavior, not only the mock runtime.
2. Make the authoring workspace feel more like a document coding-agent loop, especially around checkpoints and observable manual edits.
3. Reduce frontend bundle risk so operational surfaces do not bloat the first authoring load.
4. Make Skill Pack Management easier to maintain without turning it into the main product surface.
5. Keep plans, tests, and docs synchronized so future agents can continue without re-discovering the same boundaries.

## Scope

This plan covers four product/engineering phases plus a baseline closure phase:

- Phase 0: land the already-completed generic authoring alignment patch cleanly.
- Phase 1: harden generic authoring contracts for the real OpenHands runtime path.
- Phase 2: add explicit manual checkpoint support to the authoring workbench.
- Phase 3: split frontend routes/chunks and add bundle hygiene checks.
- Phase 4: split and simplify Skill Pack Management.

## Non-Goals

- No fixed per-document-type workflow engine.
- No template-per-document-type authoring path.
- No semantic RAG writing path as the default strategy.
- No direct DOCX editing inside the workbench.
- No large visual redesign of the authoring shell.
- No live-provider OpenHands test in normal CI; live runtime smoke remains opt-in.

## Files And Modules Likely To Change

### Current Patch Closure

- `docs/superpowers/plans/2026-05-17-generic-authoring-alignment.md`
- `docs/superpowers/completed/`
- Current modified code from the generic authoring alignment pass.

### Management Surface

- `apps/web/src/shell/management/SkillPackManager.tsx`
- New focused components under `apps/web/src/shell/management/`, likely:
  - `SkillPackList.tsx`
  - `CreatePackForm.tsx`
  - `ResourcePanel.tsx`
  - `SkillCreatorPanel.tsx`
  - `SkillArtifactEditor.tsx`
  - `ValidationPublishPanel.tsx`
- `apps/web/src/shell/management/ManagementPage.tsx`
- `apps/web/src/shell/management/__tests__/ManagementPage.test.tsx`
- `apps/web/src/shell/state/useSkillPacks.ts`
- `apps/web/src/shell/theme/shell.css` or the current management CSS owner.

### Runtime Contracts

- `services/api/docagent_api/prompts.py`
- `services/api/docagent_api/routes/sessions.py`
- `services/api/docagent_api/worker_tasks.py`
- `agent/runtime-adapters/openhands/docagent_openhands_runtime/adapter.py`
- `agent/runtime-adapters/openhands/tests/test_openhands_adapter.py`
- `services/api/tests/test_prompts.py`
- `services/api/tests/test_phase3_api.py`
- `tools/runtime/openhands_smoke.py`
- `docs/architecture/agent-runtime.md`

### Authoring Checkpoints

- `services/api/docagent_api/routes/tasks.py`
- `services/api/docagent_api/request_models.py`
- `services/api/docagent_api/response_models.py`
- `services/api/tests/test_task_checkpoints.py`
- `packages/workspace/docagent_workspace/checkpoint.py`
- `apps/web/src/api.ts`
- `apps/web/src/types.ts`
- `apps/web/src/shell/AppShell.tsx`
- `apps/web/src/shell/editor/tabs/DraftTab.tsx`
- `apps/web/src/shell/editor/tabs/__tests__/DraftTab.test.tsx`
- `apps/web/src/shell/__tests__/AppShell.test.tsx`
- `apps/web/tests/core-loop.spec.ts`
- `docs/architecture/workspace-contract.md`

### Bundle Hygiene

- `apps/web/src/App.tsx`
- `apps/web/src/shell/management/ManagementPage.tsx`
- `apps/web/src/shell/panes/EditorPane.tsx`
- `apps/web/src/shell/editor/LazyDraftEditor.tsx`
- `apps/web/vite.config.ts`
- New script: `tools/quality/check_web_bundle.py`
- `tests/test_dev_entrypoint.py` or new `tests/test_web_bundle_contract.py`
- `docs/quality/local-development.md`

## Step-By-Step Implementation Checklist

### Phase 0: Close Current Alignment Patch

- [ ] Move the completed task-sized plan from `docs/superpowers/plans/2026-05-17-generic-authoring-alignment.md` to `docs/superpowers/completed/2026-05-17-generic-authoring-alignment.md`.
- [ ] Re-run the verification suite used by the patch:

```powershell
python -m pytest packages/conversion/tests tools/import/tests packages/contracts/tests services/api/tests agent/runtime-adapters/mock/tests agent/runtime-adapters/openhands/tests tests -q
npm run test:unit -- --run
npm run test
npm run build
npm run test:e2e -- tests/core-loop.spec.ts tests/workbench-shell.spec.ts
git diff --check -- . ':!.claude/settings.local.json'
```

- [ ] Commit the generic authoring alignment patch before starting new behavior changes.
- [ ] Record the completed verification summary in the commit message or a short completion note.

Acceptance:

- The working tree has no untracked test artifacts.
- The completed plan no longer sits in `docs/superpowers/plans/`.
- The current generic authoring fixes are landed as one coherent baseline.

### Phase 1: Harden Generic Contracts For OpenHands/ACP

- [ ] Add prompt contract tests in `services/api/tests/test_prompts.py`:
  - `services/api/docagent_api/prompts.py` already exists and owns `build_prompt_bundle`; keep these as direct prompt-bundle tests rather than extracting prompt constants from route modules.
  - A memo task prompt includes `Document type: memo`.
  - A task bound to a published pack version uses the published snapshot `SKILL.md`.
  - The prompt does not mention `doc-types/prd` unless `doc_type_id == "prd"`.
  - The prompt repeats the workspace contract paths for `context/`, `draft/`, `reviews/`, and `artifacts/`.
- [ ] Add OpenHands adapter tests in `agent/runtime-adapters/openhands/tests/test_openhands_adapter.py`:
  - `FakeOpenHandsClient.create_session` captures the `PromptBundle`.
  - A non-PRD prompt bundle is forwarded unchanged to `client.create_session`.
  - The `session_created` raw event includes the dynamic `doc_type_id`.
  - File write ACP projections remain generic and do not infer PRD-specific timeline labels.
- [ ] Add API-level non-PRD runtime prompt tests in `services/api/tests/test_phase3_api.py` using a fake prompt-only adapter:
  - `loop/start` sends the generic start prompt and metadata `{"action": "start_loop"}`.
  - `artifacts/export-markdown` sends `Export the current draft to artifacts/memo-draft.md.` for a memo task.
  - Responses and ACP prompt events report the same dynamic artifact path.
- [ ] Extend `tools/runtime/openhands_smoke.py` with an optional `--doc-type` argument if it does not already support one.
- [ ] Document in `docs/architecture/agent-runtime.md` that CI covers OpenHands with fake-client contract tests, while live provider smoke remains opt-in.

Focused verification:

```powershell
python -m pytest services/api/tests/test_prompts.py services/api/tests/test_phase3_api.py agent/runtime-adapters/openhands/tests -q
python tools/runtime/openhands_smoke.py --help
```

Acceptance:

- Generic document-type behavior is proven for the real adapter boundary, not only the mock runtime.
- Live OpenHands smoke can be pointed at a second document type without editing code.
- PRD remains a seed document type, not an architectural assumption.

Rollback:

- If the live smoke extension is noisy, keep the fake-client contract tests and postpone only the CLI option.

### Phase 2: Add Manual Checkpoint Support To Authoring

- [ ] Add backend checkpoint tests in a new `services/api/tests/test_task_checkpoints.py`:
  - `POST /tasks/{task_id}/draft/checkpoints` calls the existing `docagent_workspace.checkpoint_draft(workspace_root, summary=note)` helper instead of implementing new version naming logic.
  - The response includes the helper's `version_path`, `summary`, `version`, `created_by`, and `created_at` fields.
  - If no draft exists, the endpoint returns `400`.
  - If the latest session exists, the checkpoint appears in ACP events as a semantic checkpoint event.
- [ ] Implement the endpoint in `services/api/docagent_api/routes/tasks.py`.
- [ ] Add response/request models in `response_models.py` and `request_models.py` if a note/summary field is accepted.
- [ ] Update the workspace contract in `docs/architecture/workspace-contract.md` to state that user-created checkpoints live in `versions/` and should be visible in the workspace tree.
- [ ] Add `api.createDraftCheckpoint(taskId, note)` in `apps/web/src/api.ts` and the corresponding type in `apps/web/src/types.ts`.
- [ ] Enable the disabled `+ Checkpoint` button in `DraftTab.tsx`.
- [ ] Define auto-save interaction explicitly:
  - backend checkpoint reads the server-authoritative `draft/draft.md`;
  - frontend disables the checkpoint button while `useAutoSave` reports `saving`;
  - frontend sends a final `api.updateDraft(taskId, draft)` before checkpointing when local draft text differs from the last server-saved draft.
- [ ] Wire `AppShell.tsx` so checkpoint creation invalidates:
  - `["workspace", taskId]`;
  - `["draft", taskId]` only if the backend returns changed draft content;
  - `["acp-events", sessionId]` or the existing timeline refresh path.
- [ ] Add UI tests:
  - `DraftTab` calls `onCreateCheckpoint` when clicked.
  - `AppShell` calls `api.createDraftCheckpoint` and refreshes the workspace tree.
  - The button is disabled while the active runtime session is running.
- [ ] Add one Playwright assertion to `apps/web/tests/core-loop.spec.ts`:
  - create or reach a draft;
  - click Checkpoint;
  - confirm a `versions/` file appears in the workspace tree.

Focused verification:

```powershell
python -m pytest services/api/tests/test_task_checkpoints.py packages/workspace/tests/test_checkpoint.py -q
npm run test:unit -- --run src/shell/editor/tabs/__tests__/DraftTab.test.tsx src/shell/__tests__/AppShell.test.tsx
npm run test:e2e -- tests/core-loop.spec.ts --grep "checkpoint"
```

Acceptance:

- Manual edits have an explicit checkpoint path instead of a disabled affordance.
- Checkpoints are observable in ACP/timeline and inspectable in `versions/`.
- No checkpoint can be created while the active session is running unless a later plan defines conflict handling.

Rollback:

- If UI wiring is unstable, keep the backend endpoint and hide the button behind disabled state until the next slice.

### Phase 3: Reduce Bundle And Route Coupling

- [ ] Measure the current bundle before setting a hard threshold:
  - run `npm run build`;
  - record the largest JS chunks and whether `ManagementPage` is inside the authoring initial chunk;
  - set the first hard threshold as a ratchet from the measured baseline, not as an arbitrary target.
- [ ] Add a baseline bundle contract test or script:
  - `tools/quality/check_web_bundle.py` reads `apps/web/dist/assets/*.js`.
  - It reports the largest chunks and fails if the initial route chunk exceeds the selected threshold.
  - Initial suggested ratchet: after route lazy loading, main authoring chunk must be at least 20% smaller than the measured pre-split main chunk; editor chunk is tracked separately until CodeMirror strategy is revisited.
- [ ] Lazy-load the management route in `apps/web/src/App.tsx` so Skill Pack Management is not imported by the authoring first load.
- [ ] Keep `DraftEditor` lazy-loaded and verify the CodeMirror chunk remains separate.
- [ ] Consider lazy-loading heavy tab content:
  - `DiffTab` and `react-diff-viewer-continued`;
  - Markdown preview dependencies if they are part of the initial chunk;
  - management-only panels after route-level lazy loading.
- [ ] Add Vite manual chunking only after route lazy loading if the bundle still exceeds threshold.
- [ ] Document the bundle check in `docs/quality/local-development.md`.

Focused verification:

```powershell
npm run build
python tools/quality/check_web_bundle.py apps/web/dist
npm run test:unit -- --run src/shell/__tests__/AppShell.test.tsx src/shell/management/__tests__/ManagementPage.test.tsx
```

Acceptance:

- The authoring route no longer eagerly imports the full management surface.
- Vite build either has no large initial authoring chunk warning or the remaining warning is explicitly isolated to a lazy route/editor chunk.
- Bundle thresholds are enforced by a repo-local script.

Rollback:

- Revert manual chunking first if runtime loading breaks; keep route-level lazy loading if tests remain stable.

### Phase 4: Split And Simplify Skill Pack Management

- [ ] Add focused management component tests before splitting:
  - `ManagementPage` still renders the dedicated route.
  - Resource conversion warnings remain visible.
  - Converted Markdown preview still opens from resource rows.
  - Publish remains disabled until validation passes and all warnings are acknowledged.
  - Settings drawer only links to management and does not embed the full manager.
- [ ] Split `SkillPackManager.tsx` into smaller components only after Phase 3 has removed management from the authoring first-load path:
  - `SkillPackList` owns selection and published/draft badges.
  - `CreatePackForm` owns new pack creation.
  - `ResourcePanel` owns material text/file upload, resource list, warning display, and converted Markdown preview.
  - `SkillCreatorPanel` owns Skill Creator message submission and generated artifact refresh.
  - `SkillArtifactEditor` owns `SKILL.md` editing and saving.
  - `ValidationPublishPanel` owns validate, warning acknowledgment, publish note, and publish action.
- [ ] Keep all API calls in existing hooks from `useSkillPacks.ts`; do not introduce a new client abstraction unless duplicated mutation/query logic appears after the split.
- [ ] Add dense operational layout refinements only where they clarify repeated work:
  - stable resource row sizing;
  - clear selected resource state;
  - validation warnings grouped with their acknowledgment controls;
  - no marketing copy or tutorial text in the app surface.
- [ ] Update `docs/product/ui-surfaces.md` only if the management surface contract changes.

Focused verification:

```powershell
npm run test:unit -- --run src/shell/management/__tests__/ManagementPage.test.tsx src/shell/__tests__/AppShell.test.tsx
npm run test
```

Acceptance:

- No management component should remain a grab-bag of list, upload, chat, editor, validation, and publish concerns.
- The dedicated `/management/skill-packs` route remains the only full management surface.
- Existing Skill Creator and publish safety behavior is preserved.

Rollback:

- Revert only the component split if behavior regresses; keep tests that capture warning acknowledgment and resource visibility.

### Phase 5: Review, Docs, And Release Gate

- [ ] Run the full verification suite:

```powershell
python -m pytest packages/conversion/tests tools/import/tests packages/contracts/tests services/api/tests agent/runtime-adapters/mock/tests agent/runtime-adapters/openhands/tests tests -q
npm run test:unit -- --run
npm run test
npm run build
npm run test:e2e -- tests/core-loop.spec.ts tests/workbench-shell.spec.ts
git diff --check -- . ':!.claude/settings.local.json'
```

- [ ] Update `README.md` only if startup, smoke, or verification commands changed.
- [ ] Update `docs/product/ui-surfaces.md` if management/authoring responsibilities changed.
- [ ] Update `docs/architecture/agent-runtime.md` if OpenHands smoke or contract behavior changed.
- [ ] Update `docs/architecture/workspace-contract.md` if checkpoint semantics changed.
- [ ] Move this plan from `docs/exec-plans/active/` to `docs/exec-plans/completed/` after implementation and verification.

Acceptance:

- Full verification is green or any residual risk is explicitly documented.
- The product direction remains aligned with the north star: interactive, observable, human-in-the-loop document agent workbench.

## Verification Commands

Use focused commands after each phase and the full release gate before completion:

```powershell
python -m pytest services/api/tests/test_prompts.py services/api/tests/test_phase3_api.py agent/runtime-adapters/openhands/tests -q
python -m pytest services/api/tests/test_phase2_api.py services/api/tests/test_skill_pack_routes.py services/api/tests/test_skill_packs.py -q
npm run test:unit -- --run src/shell/management/__tests__/ManagementPage.test.tsx src/shell/__tests__/AppShell.test.tsx src/shell/editor/tabs/__tests__/DraftTab.test.tsx
npm run test
npm run build
npm run test:e2e -- tests/core-loop.spec.ts tests/workbench-shell.spec.ts
git diff --check -- . ':!.claude/settings.local.json'
```

For documentation-only updates, also run:

```powershell
Get-ChildItem -Recurse -File | Select-Object FullName
```

## Rollback Or Recovery Notes

- Keep each phase as a separate commit or PR-ready slice.
- If Phase 1 component splitting causes UI regressions, revert the split but preserve behavior tests.
- If Phase 2 exposes real OpenHands prompt assumptions, land fake-client contract tests first and defer live smoke changes.
- If Phase 3 checkpoint semantics conflict with runtime edits, disable the UI button while preserving the backend endpoint and tests for idle sessions.
- If Phase 4 chunking breaks lazy routes, revert manual chunk configuration before reverting route-level lazy loading.
- Do not revert unrelated local files such as `.claude/settings.local.json`.

## Open Questions

1. Should manual checkpoint filenames continue using `checkpoint_draft`'s existing `versions/vNNN.md` sequence, or should a later change add user-note suffixes? Default recommendation: keep `versions/vNNN.md` for now to match existing agent checkpoints.
2. Should checkpoint creation be allowed when no runtime session exists? Default recommendation: yes, but without ACP event emission.
3. Should the bundle threshold be a hard CI failure immediately or a warning for one phase? Default recommendation: hard fail for the initial authoring chunk, warning for lazy editor chunks.
4. Should live OpenHands smoke become part of a nightly/manual workflow later? Default recommendation: keep it opt-in until provider credentials and runtime stability are settled.
5. Should `prd` remain a title-formatting acronym special case? Default recommendation: yes, but only in display helpers; path, prompt, event, and artifact behavior must remain `doc_type_id`-driven.

## Self-Review

- Spec coverage: The plan maps every accepted follow-up suggestion to an implementation phase: management simplification, real runtime generic coverage, authoring loop checkpointing, bundle hygiene, and release-gate review.
- Placeholder scan: No `TBD`, `TODO`, or vague "write tests" steps remain; each phase names files, behaviors, commands, and acceptance criteria.
- Type consistency: Proposed frontend API names use `createDraftCheckpoint`; backend endpoint path is consistently `/tasks/{task_id}/draft/checkpoints`; checkpoint files consistently live under `versions/`.
