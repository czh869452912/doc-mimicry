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
create_session(task_id, workspace_root, doc_type_id, prompt_bundle)
send_message(session_id, message)
start_loop(session_id)
approve_outline(session_id, outline_markdown)
revise_selection(session_id, selected_text, instruction)
run_checklist(session_id)
export_markdown(session_id)
cancel(session_id)
get_state(session_id)
```

Each operation returns product-level results:

- semantic timeline events;
- workspace paths changed;
- next session state when applicable;
- raw runtime event references when available;
- clear errors that the API can map to stable HTTP responses.

OpenHands-specific request and response types must stay inside `agent/runtime-adapters/openhands/`.

`send_message` is for free-form user turns only. The operation-specific methods are product control points that may internally send structured messages to OpenHands, but they stay separate in the interface so the backend can preserve explicit session states and HTTP endpoints.

## Session State Machine

The product backend owns DocAgent session state. Runtime-specific state can be stored as adapter metadata, but API consumers should see this stable state machine:

```text
idle
  -> running_context
  -> await_outline_approval
  -> running_draft
  -> draft_ready
  -> running_revision
  -> draft_ready
  -> running_checklist
  -> draft_ready
  -> running_export
  -> draft_ready
```

Terminal or interruption states:

```text
paused
failed
cancelled
completed
```

Valid transitions:

| Operation | Allowed From | Next State |
|---|---|---|
| `create_session` | task exists | `idle` |
| `start_loop` | `idle`, `failed` after user retry | `running_context`, then `await_outline_approval` |
| `approve_outline` | `await_outline_approval` | `running_draft`, then `draft_ready` |
| `revise_selection` | `draft_ready` | `running_revision`, then `draft_ready` |
| `run_checklist` | `draft_ready` | `running_checklist`, then `draft_ready` |
| `export_markdown` | `draft_ready` | `running_export`, then `draft_ready` |
| `send_message` | `idle`, `await_outline_approval`, `draft_ready`, `paused` | state depends on runtime result |
| `cancel` | any `running_*` state | `cancelled` |
| runtime recoverable pause | any `running_*` state | `paused` |
| runtime fatal error | any non-terminal state | `failed` |

Invalid operations should return stable API errors instead of being forwarded to OpenHands. Examples:

- `approve_outline` before `start_loop`: `409 Conflict`
- `revise_selection` before draft generation: `400 Bad Request`
- `run_checklist` before `draft_ready`: `409 Conflict`
- `cancel` after `completed` or `cancelled`: idempotent success with current state

The implementation plan should add state-transition tests before wiring OpenHands.

## Prompt Assembly And Workspace Strategy

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

Prompt assembly belongs to the product backend or a small backend helper, not to the OpenHands adapter. The adapter receives a `prompt_bundle` containing the assembled system prompt, task instruction, and path metadata. This keeps repository file layout knowledge in the product layer and keeps `OpenHandsRuntimeAdapter` focused on creating sessions, sending instructions, streaming events, and mapping runtime results.

The adapter may validate that referenced paths exist, but it should not decide which project files constitute the prompt. The prompt and doc type pack teach form; the runtime adapter supplies execution.

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

Raw runtime events should be stored separately from the semantic timeline to avoid schema churn in the existing timeline JSON. Use a session-scoped raw event log such as:

```text
.local/docagent/raw-events/{session_id}.jsonl
```

Each line should be a raw event envelope:

```json
{
  "id": "raw-...",
  "session_id": "session-...",
  "runtime": "openhands",
  "runtime_session_id": "...",
  "kind": "tool_call_started",
  "payload": {},
  "created_at": "2026-05-06T00:00:00Z"
}
```

Semantic timeline events may reference `raw_event_id`, but should not embed the raw payload.

## Streaming Protocol

Phase 3 should not redesign the frontend around streaming. The first OpenHands integration should use backend-side event ingestion plus polling from the existing timeline endpoint:

```text
OpenHands stream
  -> OpenHandsRuntimeAdapter consumes raw events
  -> DocAgentState appends raw event JSONL
  -> timeline mapper appends semantic events
  -> UI polls GET /sessions/{session_id}/timeline and GET /sessions/{session_id}
```

This keeps frontend changes small and avoids committing to SSE or WebSocket semantics before the runtime event shape is proven. SSE or WebSocket can be added later as a UI performance upgrade without changing the adapter contract.

Long-running operations should return after the product-visible phase completes or fails. The API should not hold connections forever. The implementation plan should include operation timeouts and state updates so a stuck OpenHands run becomes `failed` or `paused` with a semantic `error` event.

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

Timeout and cancellation behavior:

- every runtime operation should accept or use a configured timeout;
- timeout during a running operation should cancel or pause the OpenHands run when the runtime supports it;
- if cancellation succeeds, the product session becomes `cancelled`;
- if timeout leaves the runtime recoverable, the product session becomes `paused`;
- if timeout leaves the runtime unrecoverable, the product session becomes `failed`;
- `cancel(session_id)` should be part of the adapter contract even if the first UI only uses it from tests or an internal recovery path.

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
POST /tasks
POST /tasks/{task_id}/sessions
POST /tasks/{task_id}/inputs/text
POST /sessions/{session_id}/loop/start
GET /tasks/{task_id}/workspace/files?path=draft/outline.md
POST /sessions/{session_id}/outline/approve
GET /tasks/{task_id}/draft
POST /sessions/{session_id}/revision/selection
POST /sessions/{session_id}/checklist/run
POST /sessions/{session_id}/artifacts/export-markdown
GET /sessions/{session_id}/timeline
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
10. Raw OpenHands events are stored in a separate session-scoped raw event log.
11. Session state transitions reject invalid operations before hitting OpenHands.

## Deferred Questions

- Whether OpenHands should mount `doc-types/` read-only or receive a copied task-local snapshot.
- Whether the first OpenHands integration should use local Agent Server only or also support remote server configuration immediately.

## Pre-Adapter Cleanup

Move `utc_now()` into a shared utility module before adding OpenHands code. This avoids duplicating timestamp formatting in the product backend, workspace helpers, mock adapter, OpenHands adapter, and raw event storage.
