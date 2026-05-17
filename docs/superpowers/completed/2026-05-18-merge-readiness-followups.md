# Merge Readiness Follow-ups

## Goal

Close confirmed review findings on the generic authoring branch so it can merge back to `main` with state, checkpoint, and quality-gate behavior verified.

## Scope

- Bind manual checkpoint timeline events to the active authoring session when provided.
- Surface user-facing failures for manual checkpoint and selected-text revision actions.
- Keep `/checkpoint` aligned with draft autosave and running-session guards.
- Remove small stale/undefined UI states found in the review.
- Make the web bundle budget check executable from CI after a production build.

## Non-goals

- Redesign the authoring loop.
- Add fixed workflow or document-template behavior.
- Change runtime adapter protocol boundaries.

## Files And Modules Likely To Change

- `services/api/docagent_api/routes/tasks.py`
- `services/api/docagent_api/request_models.py`
- `services/api/tests/test_task_checkpoints.py`
- `apps/web/src/api.ts`
- `apps/web/src/shell/AppShell.tsx`
- `apps/web/src/shell/panes/ConversationPane.tsx`
- `apps/web/src/shell/panes/EditorPane.tsx`
- `apps/web/src/shell/editor/tabs/DraftTab.tsx`
- `apps/web/src/shell/management/SkillPackManager.tsx`
- `apps/web/src/shell/conversation/cards/CheckpointCard.tsx`
- `.github/workflows/ci.yml`
- Focused frontend and bundle contract tests.

## Step-by-step Implementation Checklist

- [x] Add failing backend tests for active `session_id` checkpoint attribution.
- [x] Add failing frontend tests for checkpoint session id, error feedback, and autosave guard.
- [x] Add failing tests for stale skill-pack selection, empty checkpoint paths, and bundle CI enforcement.
- [x] Implement the smallest backend and frontend changes that satisfy those tests.
- [x] Run focused tests, then broader API/web quality gates.
- [x] Run blocking `claude -p` review and address merge-blocking findings.

## Verification Commands

```powershell
python -m pytest services/api/tests/test_task_checkpoints.py tests/test_web_bundle_contract.py -q
cd apps/web
npm run test:unit -- src/shell/__tests__/AppShell.test.tsx src/shell/conversation/slashCommands.test.ts src/shell/management/__tests__/ManagementPage.test.tsx src/shell/acp/__tests__/AcpInteractionSurface.test.tsx
npm run build
cd ../..
python tools/quality/check_web_bundle.py apps/web/dist
claude -p "<review prompt>"
```

## Rollback Or Recovery Notes

If the frontend autosave guard causes unexpected editor churn, rollback only the `onSaveStateChange` plumbing and keep the backend `session_id` checkpoint attribution. If CI budget checking flakes, keep the script tests and temporarily run the budget command manually from the plan while investigating.

## Status

Completed on 2026-05-18. The blocking review pass found no merge blockers. Two non-blocking review concerns were resolved before completion: toolbar action feedback now takes priority over stale conversation status, and checkpoint session validation returns a clearer not-found-or-wrong-task message.

## Open Questions

- None.
