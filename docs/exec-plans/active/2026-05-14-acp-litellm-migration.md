# ACP Interaction Plane And LiteLLM Migration Plan

**Goal:** Replace DocAgent's custom agent interaction chain with an ACP-based session and timeline plane, and route model access through LiteLLM Proxy.

**Scope:** This plan covers backend event contracts, session routing, center timeline rendering, OpenHands compatibility, LiteLLM infrastructure, tests, and documentation. It does not build new document authoring features.

**Non-goals:** Do not redesign the authoring UI layout. Do not make the product a fixed workflow engine. Do not remove the mock runtime until ACP test coverage is stable. Do not expose runtime endpoints directly to the browser.

## Architecture

DocAgent will treat ACP events as the source of truth for agent interaction. The backend owns an ACP gateway and event store. The center timeline renders ACP events directly, while DocAgent cards are projections from those events. Agent runtimes are replaceable through ACP-native implementations or runtime-specific ACP shims.

LiteLLM Proxy becomes the model gateway used by agent runtimes. Runtime configuration should point at LiteLLM model aliases instead of provider-specific endpoints.

```text
UI Center Timeline
  <- ACP event stream

DocAgent Backend
  -> ACP session gateway
  -> ACP event store
  -> DocAgent projection layer
  -> workspace, artifacts, approvals, audit

Agent Runtime
  -> ACP-native runtime or runtime shim

LiteLLM Proxy
  -> model providers
```

## Files And Modules Likely To Change

- `packages/contracts`: add ACP envelope and projection contracts shared by backend and tests.
- `services/api`: add ACP event persistence, session prompt endpoint, event stream endpoint, and projection helpers.
- `agent/runtime-adapters`: add an ACP-compatible runtime boundary and OpenHands ACP shim.
- `packages/timeline`: replace OpenHands-first mapping with ACP projection helpers.
- `apps/web`: render ACP timeline parts and preserve existing DocAgent cards as projections.
- `docker-compose.yml`, `docker-compose.override.yml`, `.env.example`: add LiteLLM service and model gateway environment.
- `README.md`, `services/api/README.md`, `docs/architecture/agent-runtime.md`: document ACP and LiteLLM as the supported architecture.

## Step-By-Step Implementation Checklist

### Phase 1: Define The ACP Event Store Contract

- [x] Create shared ACP event envelope models.
  - Include session id, sequence number, ACP method or event type, payload, created timestamp, and optional projection metadata.
  - Keep the payload as structured JSON so newly supported ACP events do not require schema churn.
- [x] Add backend persistence for ACP events.
  - Store raw ACP event payloads separately from DocAgent semantic projections.
  - Use monotonically increasing row ids for stream resume.
- [x] Add API read endpoints for ACP events.
  - `GET /sessions/{session_id}/events`
  - `GET /sessions/{session_id}/events/stream`
- [x] Add tests proving events are append-only, ordered, resumable, and session-scoped.
- [x] Keep the current semantic timeline endpoint during this phase for compatibility.

### Phase 2: Make The Center Timeline Render ACP Events

- [x] Add frontend ACP event types.
- [x] Add timeline renderers for the core ACP event families:
  - user prompt
  - agent message chunk and completed message
  - tool call start/update/done
  - file operation
  - command or terminal operation
  - plan update
  - permission request
  - error, cancellation, and resume state
- [x] Add projection renderers for existing DocAgent cards:
  - outline review
  - draft update
  - checklist result
  - artifact
  - approval
- [x] Update timeline state to subscribe to ACP event stream as primary source.
- [x] Keep semantic timeline rendering behind a compatibility fallback until ACP end-to-end tests pass.
- [x] Add Vitest coverage for chunk merging, tool status updates, raw payload preservation, and projection card routing.

### Phase 3: Replace Operation-Specific Runtime Calls With ACP Prompts

- [ ] Add a single backend prompt endpoint:
  - `POST /sessions/{session_id}/prompt`
- [ ] Represent product actions as ACP prompts with metadata:
  - start authoring loop
  - approve outline
  - revise selection
  - run checklist
  - export artifact
- [ ] Remove new development from operation-specific runtime methods.
- [ ] Preserve existing endpoints temporarily as thin wrappers that call the new prompt endpoint with metadata.
- [ ] Add API tests proving old endpoints and new prompt endpoint produce the same workspace outcomes for the mock runtime.
- [ ] Add state-transition tests that keep DocAgent session status product-owned.

### Phase 4: Add The Runtime ACP Boundary

- [ ] Define the runtime-facing ACP session interface in the adapter layer.
  - create or load session
  - send prompt
  - stream updates
  - cancel session
- [ ] Implement an ACP mock runtime for deterministic tests.
- [ ] Wrap the current OpenHands integration in an ACP shim.
  - Convert OpenHands message events to ACP message updates.
  - Convert OpenHands tool/file/command events to ACP tool updates.
  - Preserve unsupported raw payloads in ACP event payloads rather than dropping them.
- [ ] Add tests for cancel, resume gap handling, tool update ordering, and file-write projections.
- [ ] Mark the current OpenHands-specific semantic mapper as legacy once the ACP shim is covered.

### Phase 5: Add LiteLLM Proxy As The Model Gateway

- [ ] Add a `litellm` service to Docker Compose.
- [ ] Add a checked-in LiteLLM config template with model aliases:
  - `docagent/default`
  - `docagent/fast`
  - `docagent/reasoning`
- [ ] Route OpenHands and future runtimes to LiteLLM by default in Compose.
- [ ] Keep provider credentials in environment variables or deployment secrets.
- [ ] Pin LiteLLM to a patched version and document upgrade discipline.
- [ ] Add a mock-safe config or test mode that does not require live provider credentials.
- [ ] Add smoke tests that verify runtime containers receive LiteLLM base URL and model aliases.

### Phase 6: Retire The Old Interaction Chain

- [ ] Remove the operation-specific streaming adapter methods after wrappers no longer need them.
- [ ] Stop treating semantic timeline events as the timeline source of truth.
- [ ] Keep semantic projections for product cards, reporting, and workspace invalidation.
- [ ] Update docs so new work targets ACP events and projections.
- [ ] Archive or update old OpenHands runtime adapter docs that recommend custom event mapping as the primary path.
- [ ] Add a regression test that fails if a new runtime adapter bypasses ACP event storage.

## Verification Commands

Run backend and contract tests:

```powershell
python -m pytest packages/contracts/tests packages/timeline/tests services/api/tests agent/runtime-adapters/mock/tests agent/runtime-adapters/openhands/tests -q
```

Run frontend checks:

```powershell
cd apps/web
npm run test:unit
npm run build
```

Run documentation-only structure check when this plan or ADR changes:

```powershell
Get-ChildItem -Recurse -File | Select-Object FullName
```

Run Docker config checks after LiteLLM is added:

```powershell
docker compose config
python tools/runtime/compose_smoke.py --runtime mock
```

## Rollback Or Recovery Notes

- Keep the existing semantic timeline endpoint until ACP rendering covers the authoring loop.
- Keep the mock runtime as the fallback while the OpenHands ACP shim stabilizes.
- Make old operation endpoints thin wrappers before deleting them, so frontend migration can happen gradually.
- If the OpenHands SDK cannot support reliable resume through the shim, fail clearly and keep the ACP session state product-owned rather than silently creating a new runtime conversation.
- If LiteLLM setup fails, the runtime can temporarily keep direct provider configuration, but new runtime work should still target the LiteLLM gateway contract.

## Open Questions

- Which ACP event subset should be required for the first compatible runtime?
- Should DocAgent expose raw ACP JSON in the UI by default, or behind an inspect affordance?
- Should approval prompts use ACP permission requests directly, or a DocAgent-specific projection with ACP metadata?
- Should the first OpenHands ACP shim live under `agent/runtime-adapters/openhands` or a new `agent/runtime-adapters/acp-openhands` package?
- Should LiteLLM run in every dev stack by default, or only when a real runtime is selected?
