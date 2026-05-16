# Legacy Runtime Compatibility Cleanup Plan

**Status:** Completed on 2026-05-16.

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:executing-plans to work this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decide and, if accepted, remove the legacy runtime document-action fallback path now that ACP prompt/events are the primary authoring contract.

**Architecture:** Keep the public authoring path ACP-first by making `send_prompt`
the only document-action operation. Product actions are prompts plus metadata,
not adapter methods. Keep semantic timeline data as read-model output while
this cleanup is scoped to runtime dispatch.

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

- `packages/contracts/docagent_contracts/runtime.py` exposes `RuntimeAdapter = AcpRuntimeAdapter`.
- `LegacyRuntimeAdapter` and `RuntimeEventSink` are no longer public contract exports.
- `services/api/docagent_api/routes/sessions.py` and `routes/acp_ws.py` require adapter `send_prompt` for authoring prompts.
- Background worker dispatch rejects non-`send_prompt` operation names instead of running legacy adapter methods.
- Mock and OpenHands adapters expose document actions through `send_prompt(session_id, prompt, metadata)`.
- OpenHands SDK client `send_message` / `send_message_stream` remains a runtime-specific implementation boundary, not the DocAgent adapter contract.
- ACP prompt/events remain the primary authoring path; `/timeline` remains compatibility/read-model output.

## Checklist

- [x] **Step 1: Confirm live legacy callers**

Run targeted searches:

```powershell
rg -n "LegacyRuntimeAdapter|RuntimeAdapter =|_adapter_prompt_operation|start_loop\\(|approve_outline\\(|revise_selection\\(|run_checklist\\(|export_markdown\\(" packages services agent tests docs -S
```

Classification result: live route fallback and public adapter methods were
removed; remaining `send_message` hits are OpenHands SDK client boundary code
or historical docs.

- [x] **Step 2: Choose removal or compatibility window**

Decision recorded on 2026-05-16: **Remove now.**

The ACP-native thin-client plan has been reconciled and verified, and both
runtime adapters implement `send_prompt`. Remove route-level document-action
fallback and require ACP `send_prompt` for authoring operations.

- [x] **Step 3: Update contracts and route dispatch**

If removing now:

- Remove or quarantine `LegacyRuntimeAdapter` from `runtime.py`.
- Change `RuntimeAdapter` to the ACP protocol.
- Remove `_adapter_prompt_operation`.
- Make document action routes call `send_prompt` directly, with clear error handling if an adapter does not implement it.

If keeping compatibility:

- Rename or comment the fallback as temporary compatibility.
- Add tests that make the compatibility behavior explicit and prevent it from becoming the preferred path.

- [x] **Step 4: Update runtime adapters and tests**

- Remove legacy adapter methods only after route and contract tests no longer call them.
- Keep ACP event family coverage for mock runtime.
- Keep OpenHands raw payload preservation and housekeeping-event filtering.

- [x] **Step 5: Sync docs**

- Update `docs/architecture/agent-runtime.md` and `services/api/README.md`.
- Keep `/timeline` wording scoped to compatibility/read-model output.

## Verification Commands

Last run on 2026-05-16:

- `python -m pytest packages/contracts/tests services/api/tests agent/runtime-adapters/mock/tests agent/runtime-adapters/openhands/tests -q --basetemp=.local/pytest-tmp-legacy-runtime-cleanup`: 173 passed.
- `npm run test:unit -- --run src/shell/acp/__tests__/noTimelineAuthoringContract.test.ts src/shell/acp/__tests__/noAssistantUiImports.test.ts` in `apps/web`: 2 files / 2 tests passed.
- `rg -n "projectAcpEventsToTimelineEvents|mergeProjectedAcpEvent|useDocAgentAssistantRuntime|AssistantRuntimeProvider|@assistant-ui" apps/web/src apps/web/package.json -S`: only guard-test references.

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

- If a runtime adapter still needs legacy document actions, reintroduce a private adapter helper behind `send_prompt`; do not restore route-level fallback.
- If removing legacy methods breaks worker/background operation tests, restore compatibility only as private runtime implementation details and keep route dispatch ACP-first.
- If `/timeline` removal pressure appears during this cleanup, split that into a separate plan.

## Closed Questions

- Legacy methods were removed immediately from the public DocAgent adapter contract.
- `RuntimeAdapter` is now the ACP protocol, not a compatibility union.
