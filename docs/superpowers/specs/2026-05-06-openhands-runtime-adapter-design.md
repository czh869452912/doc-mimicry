# OpenHands Runtime Adapter Design

## Context

Phase 2 proves the document authoring loop with a controlled mock runtime adapter. Phase 3 should make the runtime real without turning DocAgent Workbench into a self-built agent framework.

The product direction is to use OpenHands as the first real runtime candidate because it already provides the expensive coding-agent primitives: agent loop execution, tool handling, workspace isolation, sandbox/container behavior, command execution, file operations, event streaming, and session management. DocAgent Workbench should adapt those capabilities to the document-agent product model instead of reimplementing them.

## Goal

Connect DocAgent Workbench to a real OpenHands agent backend while preserving the Phase 2 API, workspace, timeline, and UI contracts.

The success criterion is not deleting every mock. The success criterion is that the Phase 2 PRD authoring demo path can run through `DOCAGENT_RUNTIME=openhands`, while `DOCAGENT_RUNTIME=mock` remains available for deterministic tests and local fallback.

## Non-Goals

- Do not build a custom agent loop.
- Do not build custom sandbox, tool registry, permissions, or runtime orchestration systems.
- Do not add an OpenAI Responses API tool-loop adapter in this phase.
- Do not introduce RAG as the default writing strategy.
- Do not implement production RBAC, multi-tenant billing, or full deployment hardening.
- Do not expand import/export scope beyond what Phase 2 already supports unless required for the OpenHands demo path.
- Do not make the UI depend on OpenHands-specific event payloads.

## Recommended Approach

Use a two-step Phase 3:

1. Formalize the runtime adapter boundary and move the existing mock behind it.
2. Add an OpenHands adapter as the first real runtime implementation.

This keeps the product backend runtime-agnostic and reduces development cost. The backend should know about tasks, sessions, workspace paths, semantic events, approvals, and artifacts. It should not know OpenHands private event shapes, tool internals, container policies, or agent loop mechanics.

## Architecture

```text
React Workbench UI
  -> FastAPI Product Backend
    -> Runtime Adapter Factory
      -> MockRuntimeAdapter
      -> OpenHandsRuntimeAdapter
        -> OpenHands Agent Server / SDK
          -> Isolated agent workspace
```

Runtime selection is configuration-driven:

```text
DOCAGENT_RUNTIME=mock | openhands
OPENHANDS_BASE_URL=http://127.0.0.1:...
OPENHANDS_API_KEY=...
OPENHANDS_MODEL=...
```

`mock` remains the default for tests unless a test explicitly opts into OpenHands. Local developer startup may keep mock as the safe default until OpenHands setup is documented and reliable.

## Runtime Adapter Contract

The adapter interface should cover the product operations already exposed by Phase 2:

```text
create_session(task_id, workspace_root, doc_type_id)
send_message(session_id, message)
start_loop(session_id)
approve_outline(session_id, outline_markdown)
revise_selection(session_id, selected_text, instruction)
run_checklist(session_id)
export_markdown(session_id)
get_state(session_id)
```

Each operation returns product-level results:

- semantic timeline events;
- workspace paths changed;
- next session state when applicable;
- raw runtime event references when available;
- clear errors that the API can map to stable HTTP responses.

OpenHands-specific request and response types must stay inside `agent/runtime-adapters/openhands/`.

## Workspace And Prompt Strategy

The OpenHands adapter must run against the task workspace created by the product backend.

Required readable inputs:

- `brief.md`
- `inputs/markdown/*`
- `inputs/reports/*`
- `doc-types/{doc_type}/SKILL.md`
- `doc-types/{doc_type}/examples/markdown/*`
- `doc-types/{doc_type}/examples/reports/*`
- `doc-types/{doc_type}/specs/markdown/*`
- `doc-types/{doc_type}/specs/reports/*`
- `doc-types/{doc_type}/checklists/*`
- `agent/system-prompts/docagent-core.md`

Required writable outputs:

- `context/user_intent.md`
- `context/doc_map.md`
- `context/style_notes.md`
- `context/structure_notes.md`
- `draft/outline.md`
- `draft/draft.md`
- `versions/*`
- `reviews/checklist_result.md`
- `artifacts/*`
- `logs/*`

Original binary inputs remain audit and conversion artifacts. The agent should read Markdown-facing resources by default.

The system prompt should combine:

1. `agent/system-prompts/docagent-core.md`
2. the selected doc type `SKILL.md`
3. a short runtime instruction that explains the exact workspace paths and current task/session ids

The adapter should avoid embedding document-type workflows in code. The prompt and doc type pack teach form; the runtime adapter supplies execution.

## Timeline And Events

The product timeline stays semantic. OpenHands raw events should be stored or referenced for audit, then mapped into existing semantic events where possible:

- `read_skill`
- `analyze_examples`
- `build_context`
- `extract_style`
- `extract_structure`
- `propose_outline`
- `approval_requested`
- `approve_outline`
- `update_draft`
- `create_checkpoint`
- `revise_selection`
- `run_checklist`
- `export_markdown`
- `error`

The UI should continue to consume the same semantic event shape it consumes today. Raw event payloads are for debugging and audit, not normal UI coupling.

## Human-In-The-Loop Behavior

OpenHands should do the work, but DocAgent keeps product-level control points:

- after context and outline generation, the session enters `await_outline_approval`;
- the user can edit the outline before approval;
- draft generation begins only after approval;
- selected text revision must checkpoint before modifying `draft/draft.md`;
- user messages should enter the same session instead of restarting the task.

If OpenHands has native approval or pause/resume primitives, the adapter may use them internally. The product backend should still expose stable DocAgent states.

## Error Handling

The OpenHands adapter should map runtime failures into stable product errors:

- missing configured OpenHands server: startup/configuration error;
- OpenHands session creation failed: session error with retry guidance;
- runtime lost connection: session status becomes `failed` or `paused` depending on recoverability;
- expected workspace output missing after a step: operation error that lists missing paths;
- selected text not found: same `422` behavior as Phase 2;
- draft missing before revision: same `400` behavior as Phase 2.

Failures should create semantic `error` timeline events when they occur during a user-visible operation.

## Testing Strategy

Keep most tests runtime-agnostic and deterministic:

- contract tests for adapter protocol types;
- API tests with `DOCAGENT_RUNTIME=mock`;
- adapter factory tests for runtime selection and missing configuration;
- OpenHands adapter unit tests with a fake OpenHands client;
- mapper tests from fake raw OpenHands events to semantic events.

Add a manual or opt-in integration smoke test for real OpenHands:

```text
DOCAGENT_RUNTIME=openhands
OPENHANDS_BASE_URL=...
run create task -> add input -> start loop -> approve outline -> revise -> checklist -> export
```

The real OpenHands test should assert workspace files, session states, event kinds, and artifact existence. It should not assert exact generated prose.

## Acceptance Criteria

Phase 3 is complete when:

1. `services/api` no longer directly imports `MockRuntimeAdapter`.
2. Runtime selection is handled by a factory.
3. Mock adapter still supports all Phase 2 tests.
4. OpenHands adapter can create or connect to a runtime session.
5. OpenHands can read the task workspace and doc type pack.
6. The Phase 2 PRD demo path works with `DOCAGENT_RUNTIME=openhands`.
7. Semantic timeline events remain stable for the UI.
8. Runtime-specific payloads remain isolated under the OpenHands adapter package.
9. Documentation explains local mock fallback and OpenHands setup.

## Deferred Questions

- Whether OpenHands should mount `doc-types/` read-only or receive a copied task-local snapshot.
- Whether raw runtime events should be stored in existing timeline JSON or a separate raw event log.
- Whether the first OpenHands integration should use local Agent Server only or also support remote server configuration immediately.
- Whether `utc_now()` should move to a shared utility package before runtime adapter work expands.

