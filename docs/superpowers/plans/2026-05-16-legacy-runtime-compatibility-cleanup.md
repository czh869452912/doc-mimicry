# Legacy Runtime Compatibility Cleanup Plan

**Status:** Active follow-up split from `docs/superpowers/completed/2026-05-15-acp-native-thin-client.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:executing-plans to work this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decide and, if accepted, remove the legacy runtime document-action fallback path now that ACP prompt/events are the primary authoring contract.

**Architecture:** Keep the public authoring path ACP-first by making `send_prompt`
the preferred document-action operation. Treat old document-action methods as a
temporary adapter compatibility concern, not as an authoring UI contract. Keep
semantic timeline data as read-model output while this cleanup is scoped to
runtime dispatch.

**Tech Stack:** Python 3.12, FastAPI, pytest, ACP runtime contracts, mock and OpenHands runtime adapters.

---

## Scope

- Audit every caller that still depends on `LegacyRuntimeAdapter` methods or route-level fallback dispatch.
- Decide whether legacy methods remain as compatibility aliases for one release or are removed now.
- If removing, make `send_prompt` the only document-action dispatch path for authoring operations.
- Preserve `/timeline` as compatibility/read-model output unless a separate decision removes it.

## Non-goals

- Do not change the ACP center-pane UI.
- Do not remove semantic timeline storage or projection helpers in this cleanup.
- Do not expose OpenHands directly to the browser.
- Do not change Markdown workspace rules.

## Files and modules likely to change

- `packages/contracts/docagent_contracts/runtime.py`
- `packages/contracts/tests/test_runtime_contracts.py`
- `services/api/docagent_api/routes/sessions.py`
- `services/api/tests/test_phase3_api.py`
- `services/api/tests/test_worker_tasks.py`
- `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py`
- `agent/runtime-adapters/mock/tests/`
- `agent/runtime-adapters/openhands/docagent_openhands_runtime/adapter.py`
- `agent/runtime-adapters/openhands/tests/`
- `docs/architecture/agent-runtime.md`
- `services/api/README.md`

## Step-by-step implementation checklist

## Current Code Facts

- `packages/contracts/docagent_contracts/runtime.py` still defines `LegacyRuntimeAdapter`.
- `RuntimeAdapter` is currently `AcpRuntimeAdapter | LegacyRuntimeAdapter`.
- `services/api/docagent_api/routes/sessions.py` uses `_adapter_prompt_operation` to prefer `send_prompt` and fall back to legacy document action methods.
- The route fallback spans `start_loop`, `approve_outline`, `revise_selection`, `run_checklist`, and `export_markdown`.
- Mock and OpenHands adapters still carry legacy methods for compatibility.
- ACP prompt/events remain the primary authoring path; `/timeline` remains compatibility/read-model output.

## Checklist

- [ ] **Step 1: Confirm live legacy callers**

Run targeted searches:

```powershell
rg -n "LegacyRuntimeAdapter|RuntimeAdapter =|_adapter_prompt_operation|start_loop\\(|approve_outline\\(|revise_selection\\(|run_checklist\\(|export_markdown\\(" packages services agent tests docs -S
```

Classify each hit as contract, route fallback, adapter compatibility method, test, or historical documentation.

- [ ] **Step 2: Choose removal or compatibility window**

Record the decision in this plan before editing code:

- Remove now: delete the route fallback and require ACP `send_prompt` for document actions.
- Compatibility window: keep fallback, but make docs/tests explicit that it is temporary and add a target removal condition.

- [ ] **Step 3: Update contracts and route dispatch**

If removing now:

- Remove or quarantine `LegacyRuntimeAdapter` from `runtime.py`.
- Change `RuntimeAdapter` to the ACP protocol.
- Remove `_adapter_prompt_operation`.
- Make document action routes call `send_prompt` directly, with clear error handling if an adapter does not implement it.

If keeping compatibility:

- Rename or comment the fallback as temporary compatibility.
- Add tests that make the compatibility behavior explicit and prevent it from becoming the preferred path.

- [ ] **Step 4: Update runtime adapters and tests**

- Remove legacy adapter methods only after route and contract tests no longer call them.
- Keep ACP event family coverage for mock runtime.
- Keep OpenHands raw payload preservation and housekeeping-event filtering.

- [ ] **Step 5: Sync docs**

- Update `docs/architecture/agent-runtime.md` and `services/api/README.md`.
- Keep `/timeline` wording scoped to compatibility/read-model output.

## Verification Commands

```powershell
python -m pytest packages/contracts/tests services/api/tests agent/runtime-adapters/mock/tests agent/runtime-adapters/openhands/tests -q --basetemp=.local/pytest-tmp-legacy-runtime-cleanup
```

```powershell
cd apps/web
npm run test:unit -- --run src/shell/acp/__tests__/noTimelineAuthoringContract.test.ts src/shell/acp/__tests__/noAssistantUiImports.test.ts
```

```powershell
rg -n "projectAcpEventsToTimelineEvents|mergeProjectedAcpEvent|useDocAgentAssistantRuntime|AssistantRuntimeProvider|@assistant-ui" apps/web/src apps/web/package.json -S
```

## Rollback And Recovery

- If a runtime adapter still needs legacy document actions, keep the fallback for one release and document the removal condition.
- If removing legacy methods breaks worker/background operation tests, restore the compatibility method names only at the adapter boundary and keep route dispatch ACP-first.
- If `/timeline` removal pressure appears during this cleanup, split that into a separate plan.

## Open Questions

- Should legacy methods be removed immediately, or kept until one release after OpenHands ACP runtime validation?
- Should `RuntimeAdapter` remain a union for compatibility tests, or should compatibility be represented by a separate private protocol?
