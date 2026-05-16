# ACP-Native Thin Client Implementation Plan

> **Completion note (2026-05-16):** This plan has been reconciled against live
> code and moved to `docs/superpowers/completed/`. The ACP-native center-pane
> implementation, runtime naming, backend ACP event source, and authoring UI
> guard tests are present. The remaining legacy runtime compatibility cleanup
> has been completed in `docs/superpowers/completed/2026-05-16-legacy-runtime-compatibility-cleanup.md`.
>
> Verification run before archival:
> - `npm run test:unit -- --run` in `apps/web`: 25 test files and 117 tests passed.
> - `npm run build` in `apps/web`: build passed; Vite reported only the existing large-chunk warning.
> - `python -m pytest packages/contracts/tests packages/timeline/tests services/api/tests agent/runtime-adapters/mock/tests agent/runtime-adapters/openhands/tests tests/test_litellm_compose.py tests/test_dev_entrypoint.py -q --basetemp=.local/pytest-tmp-acp-thin-final`: 208 tests passed.
> - `docker compose config`: exited 0 and rendered `DOCAGENT_RUNTIME: mock-acp`, `DOCAGENT_ACP_RUNTIME_URL`, LiteLLM, and compatibility `OPENHANDS_BASE_URL` entries.
> - `rg -n "OPENHANDS_CONTAINER_BASE_URL|DOCAGENT_RUNTIME=mock$|DOCAGENT_RUNTIME=openhands$" .env.example docker-compose.override.yml scripts/dev.ps1 README.md services/api/README.md docs/architecture docs/product docs/quality`: no matches.

> **Status note (2026-05-16):** This plan partially reflects work that has
> already landed in the repository. The center pane now has an ACP-native
> surface, assistant-ui is no longer a package dependency, runtime names are
> `mock-acp` / `openhands-acp`, and `/events` is the authoring event source.
> Before executing unchecked steps, reconcile the checklist against live code
> and update this plan instead of replaying tasks blindly. The checkbox
> walkthrough below is historical implementation detail; use the reconciliation
> table in this document as the current execution state.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace DocAgent's center-pane assistant-ui/timeline-projection chain with an ACP-native thin interaction surface, then tighten backend/runtime/deployment boundaries around the ACP event log.

**Architecture:** The React workbench keeps the current three-column shell, but the center pane reads `AcpEvent[]` directly through a local `AcpInteractionSurface` package. The backend remains the mediator between UI and runtimes, persists all interaction updates as ACP event envelopes, and treats semantic timeline data only as compatibility/read-model output. Runtime and deployment settings move toward explicit `mock-acp` and `openhands-acp` contracts while preserving the existing mock path for CI.

**Tech Stack:** React 19, Vite 7, TypeScript 5.8, TanStack Query, lucide-react, FastAPI, SQLAlchemy, Celery, pytest, Vitest, Playwright, Docker Compose, OpenHands ACP, LiteLLM.

---

## References

- Spec: `docs/superpowers/specs/2026-05-15-acp-native-thin-client-design.md`
- Current UI truth: `docs/product/ui-surfaces.md`
- ACP decision: `docs/decisions/2026-05-14-acp-interaction-plane-and-litellm-gateway.md`
- Runtime boundary: `docs/architecture/agent-runtime.md`
- Event model: `docs/architecture/event-model.md`
- Frontend third-party checklist: `docs/quality/frontend-component-integration-checklist.md`

## Reconciliation Status (2026-05-16)

The original checklist still uses unchecked task boxes, but most of the ACP
thin-client work has landed. Treat the task bodies below as reference notes,
not as a command queue.

| Task | Current state | Code facts |
| --- | --- | --- |
| 1. Add ACP Event Helpers And Contract Tests | Implemented | `apps/web/src/shell/acp/acpEvents.ts` and `apps/web/src/shell/acp/__tests__/acpEvents.test.ts` cover event classification, merging, invalidation hints, reload input, and text extraction. |
| 2. Change Timeline State To Return ACP Events | Implemented | `apps/web/src/shell/state/useTimeline.ts` stores `AcpEvent[]`, loads `api.getAcpEvents`, streams `streamAcpEventsUrl`, and derives product invalidation from ACP events. |
| 3. Build ACP Interaction Surface And Renderer | Implemented | `AcpInteractionSurface.tsx`, `AcpEventRenderer.tsx`, and `AcpRenderSlots.tsx` render ACP-native messages plus product-card read models. |
| 4. Build Local ACP Composer | Implemented | `AcpComposer.tsx`, `DocAgentSlashCommands.tsx`, and `AcpComposer.test.tsx` cover draft input, commands, send, cancel, reload, and attachments. |
| 5. Integrate ACP Surface Into ConversationPane | Implemented | `ConversationPane.tsx` accepts `AcpEvent[]` and renders either the local `AcpInteractionSurface` or configured external `AcpUiEmbed`. |
| 6. Replace Assistant UI Styling And Remove Assistant Runtime Code | Implemented for the authoring path | `@assistant-ui/*` is absent from `apps/web/package.json`; `apps/web/src/shell/acp/__tests__/noAssistantUiImports.test.ts` guards the five core ACP package files against assistant-ui imports; `apps/web/src/shell/theme/acp.css` is imported by `styles.css`. Broader authoring-path files such as `ConversationPane.tsx` and `AppShell.tsx` are covered by the timeline authoring guard, not by a global assistant-ui import guard. |
| 7. Backend ACP Event Store Guards | Mostly implemented | `_shared.py` appends ACP prompt/status/error/projection/runtime updates and maps OpenHands raw runtime events through `map_openhands_raw_event` into both legacy timeline entries and ACP projection entries. `services/api/tests/test_acp_events.py` covers `/events`, `/events/stream`, Last-Event-ID, WebSocket ACP operations, and session/task scoping. `/timeline` remains as compatibility/read-model output. |
| 8. Expand Mock ACP Runtime Coverage | Implemented | Mock runtime tests require message, tool, file, permission, status, and unknown ACP event families. |
| 9. Tighten OpenHands ACP Shim Boundary | Implemented with one intentional behavior change | OpenHands adapter tests preserve raw unknown payloads and filter housekeeping events such as `session_created`; the original expected emitted creation event should not be reintroduced without a new decision. |
| 10. Runtime Names And Deployment Configuration | Implemented | `runtime_factory.py`, `.env.example`, `docker-compose.override.yml`, `scripts/dev.ps1`, and `tests/test_dev_entrypoint.py` use canonical `mock-acp` / `openhands-acp` names while preserving migration aliases where needed. |
| 11. Deprecate `/timeline` Authoring UI Consumers | Implemented for authoring UI | `apps/web/src/api.ts` has ACP event APIs for the workbench path, guard tests block old timeline authoring helpers, and `TimelineEvent` remains only for projections/read models. |
| 12. Full Verification And Documentation Sync | Open | This reconciliation did not run the full frontend, backend, package, compose, and documentation verification bundle. Run it before moving this plan to `docs/superpowers/completed/`. |

## Remaining Follow-Up

- Run the full verification bundle from Task 12 before claiming the ACP-native
  thin-client plan is complete.
- Decide whether to remove the legacy runtime compatibility layer or split that
  cleanup into a separate compatibility-retirement plan. The cleanup is broader
  than deleting `LegacyRuntimeAdapter`: `packages/contracts/docagent_contracts/runtime.py`
  defines the protocol, while `services/api/docagent_api/routes/sessions.py`
  uses `_adapter_prompt_operation` to prefer `send_prompt` and fall back to
  legacy document action methods across `start_loop`, `approve_outline`,
  `revise_selection`, `run_checklist`, and `export_markdown`.
- Keep `/timeline` documented as compatibility/read-model output unless a new
  decision removes it entirely; it is no longer the authoring source for the
  center pane.
- After verification, either move this plan to `docs/superpowers/completed/` or
  replace it with a smaller follow-up plan that contains only the legacy
  compatibility cleanup.

## Scope

- Build a local ACP-native center-pane package in `apps/web/src/shell/acp`.
- Keep product cards by moving them behind ACP render slots.
- Change frontend state from `TimelineEvent[]` to `AcpEvent[]` for the center pane.
- Remove assistant-ui from the core conversation path and package dependencies after parity tests pass.
- Strengthen backend tests so authoring UI and runtime updates cannot rely on semantic timeline as the interaction source.
- Keep the temporary OpenHands shim only in the runtime adapter boundary.
- Update runtime/deployment names and docs toward `mock-acp` and `openhands-acp`.

## Non-Goals

- Do not redesign the full workbench layout.
- Do not expose OpenHands directly to the browser.
- Do not adopt AionUi as the product shell.
- Do not remove all semantic timeline storage in the first pass; keep compatibility/reporting until consumers are gone.
- Do not change Markdown workspace rules.
- Do not add enterprise auth/RBAC beyond enforcing current session-to-task scoping.

## File Map

Frontend ACP package:

- Create `apps/web/src/shell/acp/acpEvents.ts`: classify `AcpEvent` families, merge streaming deltas, extract text/paths/status, derive invalidation hints, and find reload input.
- Create `apps/web/src/shell/acp/AcpInteractionSurface.tsx`: local stable center-pane interface and shell composition.
- Create `apps/web/src/shell/acp/AcpEventRenderer.tsx`: message/tool/file/permission/status/unknown event rendering.
- Create `apps/web/src/shell/acp/AcpComposer.tsx`: local composer with slash commands, text input, attachment chips, send, cancel, queued draft support.
- Create `apps/web/src/shell/acp/AcpRenderSlots.tsx`: adapters from ACP events to existing DocAgent product cards.
- Create `apps/web/src/shell/acp/__tests__/acpEvents.test.ts`: pure event classification, merging, invalidation, reload tests.
- Create `apps/web/src/shell/acp/__tests__/AcpInteractionSurface.test.tsx`: render and action tests without assistant-ui.
- Create `apps/web/src/shell/acp/__tests__/AcpComposer.test.tsx`: composer, queued draft, slash, attachments, send/cancel tests.

Frontend integration:

- Modify `apps/web/src/shell/state/useTimeline.ts`: return ACP events directly and keep compatibility fallback out of center-pane state.
- Modify `apps/web/src/shell/panes/ConversationPane.tsx`: remove `AssistantRuntimeProvider`, use `AcpInteractionSurface`, and move reload logic to ACP helpers.
- Modify `apps/web/src/shell/AppShell.tsx`: pass `AcpEvent[]` through the conversation path and keep workspace invalidation behavior.
- Modify `apps/web/src/shell/theme/assistant-ui.css`: rename or replace with ACP-specific styles.
- Modify `apps/web/src/main.tsx` or the stylesheet import site: import the renamed ACP stylesheet.
- Modify `apps/web/src/types.ts`: keep `AcpEvent`; remove center-pane `raw_acp_event` dependency from `TimelineEvent` only when no remaining consumer needs it.
- Modify or delete assistant-ui-specific tests under `apps/web/src/shell/assistant/__tests__`, `apps/web/src/shell/panes/__tests__`, and `apps/web/tests/workbench-shell.spec.ts`.
- Delete `apps/web/src/shell/assistant/*` after parity.
- Delete `apps/web/src/shell/conversation/acpTimeline.ts` after parity.
- Delete `apps/web/src/shell/conversation/docagentRuntime.ts` only after no code imports `mergeTimelineEvents` or `replaceWithIdDedup`.
- Modify `apps/web/package.json` and lockfile: remove `@assistant-ui/react` and `@assistant-ui/core`.

Backend and runtime:

- Modify `services/api/docagent_api/routes/_shared.py`: add ACP-native append helpers for user prompts, session status, runtime failures, and raw runtime wrapping; stop emitting projection events for center-thread-only cases.
- Modify `services/api/docagent_api/routes/sessions.py`: ensure `/events` and `/events/stream` are the authoring source, keep `/timeline` compatibility, and add clearer session/task scoping checks.
- Modify `services/api/docagent_api/worker_tasks.py`: make worker failure/status updates emit ACP events before compatibility timeline events.
- Modify `services/api/docagent_api/runtime_factory.py`: accept `mock-acp` and `openhands-acp` as canonical runtime names while keeping `mock` and `openhands` aliases during migration.
- Modify `packages/contracts/docagent_contracts/runtime.py`: remove or quarantine `LegacyRuntimeAdapter` after backend no longer calls legacy document action methods.
- Modify `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py`: make mock ACP updates cover message, tool, file, permission, status, and unknown families.
- Modify `agent/runtime-adapters/openhands/docagent_openhands_runtime/adapter.py`: ensure shimmed OpenHands updates are only emitted as ACP envelopes, with raw payload preservation.
- Modify `agent/runtime-adapters/openhands/docagent_openhands_runtime/client.py`: rename config to ACP runtime terminology where possible and isolate OpenHands-specific resume limitations.
- Add/modify tests in `services/api/tests/test_acp_events.py`, `services/api/tests/test_phase3_api.py`, `services/api/tests/test_worker_tasks.py`, `packages/contracts/tests/test_runtime_contracts.py`, `agent/runtime-adapters/mock/tests`, and `agent/runtime-adapters/openhands/tests`.

Deployment and docs:

- Modify `docker-compose.yml`, `docker-compose.override.yml`, `.env.example`, `scripts/dev.ps1`, `start-dev.cmd`, `tools/runtime/compose_smoke.py`.
- Modify `README.md`, `services/api/README.md`, `docs/architecture/event-model.md`, `docs/architecture/agent-runtime.md`, `docs/product/ui-surfaces.md`, and `docs/quality/local-development.md`.
- Modify `tests/test_litellm_compose.py` and `tests/test_dev_entrypoint.py`.

---

## Task 1: Add ACP Event Helpers And Contract Tests

**Files:**
- Create: `apps/web/src/shell/acp/acpEvents.ts`
- Test: `apps/web/src/shell/acp/__tests__/acpEvents.test.ts`

- [ ] **Step 1: Write failing ACP helper tests**

Create `apps/web/src/shell/acp/__tests__/acpEvents.test.ts` with:

```ts
import type { AcpEvent } from "../../../types";
import {
  classifyAcpEvent,
  deriveAcpInvalidationHints,
  findReloadInput,
  mergeAcpEvents,
  textFromAcpEvent,
} from "../acpEvents";

function acp(overrides: Partial<AcpEvent> & Pick<AcpEvent, "id" | "sequence" | "event_type">): AcpEvent {
  return {
    session_id: "session-1",
    payload: {},
    projection: {},
    created_at: "2026-05-15T00:00:00Z",
    ...overrides,
  };
}

describe("ACP event helpers", () => {
  it("classifies required ACP event families from event_type and payload", () => {
    expect(classifyAcpEvent(acp({ id: "m", sequence: 1, event_type: "message_delta" })).family).toBe("message");
    expect(classifyAcpEvent(acp({ id: "t", sequence: 2, event_type: "tool/call" })).family).toBe("tool");
    expect(classifyAcpEvent(acp({ id: "f", sequence: 3, event_type: "file/write" })).family).toBe("file");
    expect(classifyAcpEvent(acp({ id: "p", sequence: 4, event_type: "permission/request" })).family).toBe("permission");
    expect(classifyAcpEvent(acp({ id: "s", sequence: 5, event_type: "session/cancelled" })).family).toBe("status");
    expect(classifyAcpEvent(acp({ id: "u", sequence: 6, event_type: "vendor/custom" })).family).toBe("unknown");
  });

  it("extracts user and assistant text from ACP payloads without projection", () => {
    expect(textFromAcpEvent(acp({
      id: "u",
      sequence: 1,
      event_type: "docagent/prompt",
      payload: { prompt: "Write the PRD" },
    }))).toBe("Write the PRD");
    expect(textFromAcpEvent(acp({
      id: "a",
      sequence: 2,
      event_type: "message_delta",
      payload: { role: "assistant", content: "Working" },
    }))).toBe("Working");
  });

  it("merges message deltas by message id and keeps sequence ordering", () => {
    const merged = mergeAcpEvents([
      acp({ id: "a1", sequence: 1, event_type: "message_delta", payload: { message_id: "m1", content: "Hel" } }),
      acp({ id: "a2", sequence: 2, event_type: "message_delta", payload: { message_id: "m1", content: "lo" } }),
      acp({ id: "tool", sequence: 3, event_type: "tool/call", payload: { id: "tool-1", name: "write_file" } }),
    ]);

    expect(merged.map((event) => event.id)).toEqual(["acp-message-m1", "tool"]);
    expect(textFromAcpEvent(merged[0])).toBe("Hello");
    expect(merged[0].sequence).toBe(2);
  });

  it("derives workspace, draft, and session invalidation hints from ACP events", () => {
    const hints = deriveAcpInvalidationHints([
      acp({ id: "file", sequence: 1, event_type: "file/write", payload: { path: "draft/draft.md" } }),
      acp({ id: "status", sequence: 2, event_type: "session/completed", payload: {} }),
    ]);

    expect(hints).toEqual({
      workspace: true,
      draft: true,
      sessions: true,
      paths: ["draft/draft.md"],
    });
  });

  it("finds reload input from previous user prompt events", () => {
    const events = [
      acp({ id: "u1", sequence: 1, event_type: "docagent/prompt", payload: { prompt: "First" } }),
      acp({ id: "a1", sequence: 2, event_type: "message_delta", payload: { role: "assistant", content: "Answer" } }),
      acp({ id: "u2", sequence: 3, event_type: "docagent/prompt", payload: { prompt: "Second" } }),
    ];

    expect(findReloadInput(events, "a1")).toBe("First");
    expect(findReloadInput(events, null)).toBe("Second");
  });
});
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
cd apps/web
npm run test:unit -- --run src/shell/acp/__tests__/acpEvents.test.ts
```

Expected: FAIL because `apps/web/src/shell/acp/acpEvents.ts` does not exist.

- [ ] **Step 3: Implement ACP helper module**

Create `apps/web/src/shell/acp/acpEvents.ts`:

```ts
import type { AcpEvent } from "../../types";

export type AcpEventFamily = "message" | "tool" | "file" | "permission" | "status" | "unknown";
export type AcpDisplayStatus = "running" | "succeeded" | "failed" | "cancelled" | "pending";

export interface ClassifiedAcpEvent {
  family: AcpEventFamily;
  role: "user" | "assistant" | "tool" | "system";
  status: AcpDisplayStatus;
  title: string;
  paths: string[];
}

export interface AcpInvalidationHints {
  workspace: boolean;
  draft: boolean;
  sessions: boolean;
  paths: string[];
}

export function classifyAcpEvent(event: AcpEvent): ClassifiedAcpEvent {
  const eventType = event.event_type.toLowerCase();
  const family = familyForEvent(event);
  return {
    family,
    role: roleForEvent(event, family),
    status: statusForEventType(eventType, event.payload.status),
    title: titleForEvent(event, family),
    paths: pathsFromAcpEvent(event),
  };
}

export function mergeAcpEvents(events: AcpEvent[]): AcpEvent[] {
  const byId = new Map<string, AcpEvent>();
  const order: string[] = [];

  for (const event of [...events].sort((a, b) => a.sequence - b.sequence)) {
    const mergeId = mergeIdForEvent(event);
    const existing = byId.get(mergeId);
    if (!existing) {
      const normalized = mergeId === event.id ? event : { ...event, id: mergeId };
      byId.set(mergeId, normalized);
      order.push(mergeId);
      continue;
    }
    byId.set(mergeId, mergeEvent(existing, event, mergeId));
  }

  return order.map((id) => byId.get(id)).filter((event): event is AcpEvent => Boolean(event));
}

export function textFromAcpEvent(event: AcpEvent): string {
  return (
    stringValue(event.payload.prompt)
    ?? stringValue(event.payload.content)
    ?? stringValue(event.payload.delta)
    ?? stringValue(event.payload.message)
    ?? stringValue(event.projection.summary)
    ?? ""
  );
}

export function pathsFromAcpEvent(event: AcpEvent): string[] {
  const payloadPaths = stringArray(event.payload.paths);
  const projectionPaths = stringArray(event.projection.paths);
  const path = stringValue(event.payload.path);
  return uniqueStrings([...payloadPaths, ...(path ? [path] : []), ...projectionPaths]);
}

export function deriveAcpInvalidationHints(events: AcpEvent[]): AcpInvalidationHints {
  const paths = uniqueStrings(events.flatMap(pathsFromAcpEvent));
  const hasStatus = events.some((event) => classifyAcpEvent(event).family === "status");
  return {
    workspace: paths.length > 0,
    draft: paths.some((path) => path.startsWith("draft/")),
    sessions: hasStatus || events.some((event) => event.event_type.toLowerCase().includes("error")),
    paths,
  };
}

export function findReloadInput(events: AcpEvent[], parentEventId: string | null): string | null {
  const merged = mergeAcpEvents(events);
  const parentIndex = parentEventId
    ? merged.findIndex((event) => event.id === parentEventId)
    : merged.length;
  const endIndex = parentIndex >= 0 ? parentIndex : merged.length;

  for (let index = endIndex - 1; index >= 0; index -= 1) {
    const event = merged[index];
    if (classifyAcpEvent(event).role === "user") {
      const input = textFromAcpEvent(event).trim();
      if (input) return input;
    }
  }
  return null;
}

function familyForEvent(event: AcpEvent): AcpEventFamily {
  const eventType = event.event_type.toLowerCase();
  if (eventType.includes("message") || eventType.includes("prompt") || eventType.includes("session/update")) return "message";
  if (eventType.includes("tool") || eventType.includes("command") || eventType.includes("terminal")) return "tool";
  if (eventType.includes("file")) return "file";
  if (eventType.includes("permission") || eventType.includes("approval")) return "permission";
  if (eventType.includes("session/") || eventType.includes("status") || eventType.includes("cancel") || eventType.includes("error")) return "status";
  return "unknown";
}

function roleForEvent(event: AcpEvent, family: AcpEventFamily): ClassifiedAcpEvent["role"] {
  const role = stringValue(event.payload.role) ?? stringValue(event.projection.actor);
  if (role === "user") return "user";
  if (role === "tool") return "tool";
  if (role === "system") return "system";
  if (family === "tool" || family === "file") return "tool";
  if (family === "permission" || family === "status") return "system";
  return "assistant";
}

function titleForEvent(event: AcpEvent, family: AcpEventFamily): string {
  const projected = stringValue(event.projection.summary);
  if (projected) return projected;
  if (family === "message") return roleForEvent(event, family) === "user" ? "You" : "Agent";
  if (family === "tool") return stringValue(event.payload.name) ?? stringValue(event.payload.tool_name) ?? "Tool";
  if (family === "file") return stringValue(event.payload.path) ?? "File activity";
  if (family === "permission") return "Permission requested";
  if (family === "status") return "Session status";
  return event.event_type;
}

function statusForEventType(eventType: string, payloadStatus: unknown): AcpDisplayStatus {
  const status = stringValue(payloadStatus);
  if (status === "failed" || status === "cancelled" || status === "pending" || status === "running" || status === "succeeded") return status;
  if (eventType.includes("fail") || eventType.includes("error")) return "failed";
  if (eventType.includes("cancel")) return "cancelled";
  if (eventType.includes("request")) return "pending";
  if (eventType.includes("complete") || eventType.includes("result") || eventType.includes("done")) return "succeeded";
  return "running";
}

function mergeIdForEvent(event: AcpEvent): string {
  if (classifyAcpEvent(event).family !== "message") return event.id;
  const messageId = stringValue(event.payload.message_id) ?? stringValue(event.payload.id);
  return messageId ? `acp-message-${messageId}` : event.id;
}

function mergeEvent(existing: AcpEvent, incoming: AcpEvent, mergeId: string): AcpEvent {
  const existingText = textFromAcpEvent(existing);
  const incomingText = textFromAcpEvent(incoming);
  const nextPayload = {
    ...existing.payload,
    ...incoming.payload,
    content: existingText + incomingText,
  };
  return {
    ...incoming,
    id: mergeId,
    payload: nextPayload,
    projection: { ...existing.projection, ...incoming.projection },
  };
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function uniqueStrings(values: string[]): string[] {
  return [...new Set(values.filter((value) => value.length > 0))];
}
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```powershell
cd apps/web
npm run test:unit -- --run src/shell/acp/__tests__/acpEvents.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/web/src/shell/acp/acpEvents.ts apps/web/src/shell/acp/__tests__/acpEvents.test.ts
git commit -m "feat(web): add acp event helpers"
```

## Task 2: Change Timeline State To Return ACP Events

**Files:**
- Modify: `apps/web/src/shell/state/useTimeline.ts`
- Modify: `apps/web/src/shell/__tests__/useTimeline.test.tsx`
- Modify: `apps/web/src/shell/state/__tests__/useTimeline.test.tsx`

- [ ] **Step 1: Update hook tests to expect ACP events, not projected timeline events**

In both `useTimeline` test files, replace expectations that read projected `TimelineEvent.kind` or fallback timeline payloads with `AcpEvent` expectations. Add this test to `apps/web/src/shell/state/__tests__/useTimeline.test.tsx`:

```ts
it("returns ACP events directly and does not fetch semantic timeline fallback", async () => {
  vi.mocked(api.getAcpEvents).mockResolvedValueOnce([
    {
      id: "acp-1",
      session_id: "session-1",
      sequence: 1,
      event_type: "message_delta",
      payload: { role: "assistant", content: "Hello" },
      projection: {},
      created_at: "2026-05-15T00:00:00Z",
    },
  ]);

  const { result } = renderHook(() => useTimeline("session-1", "task-1"), { wrapper });

  await vi.waitFor(() => expect(result.current.events.map((event) => event.id)).toEqual(["acp-1"]));
  expect(api.getTimeline).not.toHaveBeenCalled();
});
```

Add this SSE test if it does not already exist in ACP form:

```ts
it("appends ACP SSE events without projecting them", async () => {
  vi.mocked(api.getAcpEvents).mockResolvedValueOnce([]);
  const eventSources: FakeEventSource[] = [];
  vi.stubGlobal("EventSource", class extends FakeEventSource {
    constructor(url: string) {
      super(url);
      eventSources.push(this);
    }
  });

  const { result } = renderHook(() => useTimeline("session-1", "task-1"), { wrapper });
  await vi.waitFor(() => expect(eventSources).toHaveLength(1));

  eventSources[0].emit({
    id: "acp-sse-1",
    session_id: "session-1",
    sequence: 2,
    event_type: "file/write",
    payload: { path: "draft/draft.md" },
    projection: {},
    created_at: "2026-05-15T00:00:00Z",
  });

  await vi.waitFor(() => expect(result.current.events.map((event) => event.id)).toEqual(["acp-sse-1"]));
});
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
cd apps/web
npm run test:unit -- --run src/shell/state/__tests__/useTimeline.test.tsx src/shell/__tests__/useTimeline.test.tsx
```

Expected: FAIL because `useTimeline` still returns `TimelineEvent[]` and calls `api.getTimeline` when ACP events are empty.

- [ ] **Step 3: Refactor `useTimeline` to store ACP events**

Replace `apps/web/src/shell/state/useTimeline.ts` with an ACP-first implementation shaped like:

```ts
import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, streamAcpEventsUrl } from "../../api";
import type { AcpEvent } from "../../types";
import { deriveAcpInvalidationHints, mergeAcpEvents } from "../acp/acpEvents";

const TIMELINE_POLL_INTERVAL_MS = 3000;
const SSE_BACKOFF_BASE_MS = 1000;
const SSE_BACKOFF_MAX_MS = 30_000;

export function useTimeline(
  sessionId: string | null | undefined,
  taskId: string | null | undefined,
) {
  const queryClient = useQueryClient();
  const [events, setEvents] = useState<AcpEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const invalidatedEventIdsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    invalidatedEventIdsRef.current.clear();
  }, [sessionId, taskId]);

  const invalidateRelatedQueries = useCallback(
    (eventsToInspect: AcpEvent[]) => {
      const freshEvents = eventsToInspect.filter((event) => {
        if (invalidatedEventIdsRef.current.has(event.id)) return false;
        invalidatedEventIdsRef.current.add(event.id);
        return true;
      });
      const hints = deriveAcpInvalidationHints(freshEvents);
      if (hints.workspace) void queryClient.invalidateQueries({ queryKey: ["workspace", taskId] });
      if (hints.draft) void queryClient.invalidateQueries({ queryKey: ["draft", taskId] });
      if (hints.sessions) void queryClient.invalidateQueries({ queryKey: ["sessions", taskId] });
    },
    [queryClient, taskId],
  );

  const loadTimeline = useCallback(
    async (sid: string | null | undefined, shouldApply: () => boolean = () => true) => {
      if (!sid) {
        if (shouldApply()) {
          setEvents([]);
          setError(null);
          setLoading(false);
        }
        return [];
      }
      setLoading(true);
      setError(null);
      try {
        const acpEvents = mergeAcpEvents(await api.getAcpEvents(sid));
        if (shouldApply()) {
          setEvents(acpEvents);
          invalidateRelatedQueries(acpEvents);
        }
        return acpEvents;
      } catch (caught) {
        if (shouldApply()) setError(caught instanceof Error ? caught.message : "Could not refresh ACP events");
        return [];
      } finally {
        if (shouldApply()) setLoading(false);
      }
    },
    [invalidateRelatedQueries],
  );

  const refreshTimeline = useCallback(
    async () => loadTimeline(sessionId),
    [loadTimeline, sessionId],
  );

  useEffect(() => {
    let cancelled = false;
    void loadTimeline(sessionId, () => !cancelled);
    return () => {
      cancelled = true;
    };
  }, [loadTimeline, sessionId]);

  useEffect(() => {
    if (!sessionId) return;
    const currentSessionId = sessionId;
    let cancelled = false;
    let pollId: ReturnType<typeof window.setInterval> | undefined;
    let reconnectId: ReturnType<typeof window.setTimeout> | undefined;
    let backoffMs = SSE_BACKOFF_BASE_MS;
    let closeCurrentSource: (() => void) | undefined;

    function startPolling() {
      pollId = window.setInterval(() => {
        void loadTimeline(currentSessionId, () => !cancelled);
      }, TIMELINE_POLL_INTERVAL_MS);
    }

    function connect() {
      closeCurrentSource?.();
      closeCurrentSource = undefined;
      if (typeof window.EventSource !== "function") {
        startPolling();
        return;
      }
      const source = new EventSource(streamAcpEventsUrl(currentSessionId));
      closeCurrentSource = () => source.close();

      source.onmessage = (ev: MessageEvent) => {
        if (cancelled) return;
        backoffMs = SSE_BACKOFF_BASE_MS;
        try {
          const acpEvent = JSON.parse(ev.data as string) as AcpEvent;
          setEvents((prev) => mergeAcpEvents([...prev, acpEvent]));
          invalidateRelatedQueries([acpEvent]);
          if (deriveAcpInvalidationHints([acpEvent]).sessions) {
            void loadTimeline(currentSessionId, () => !cancelled);
          }
        } catch {
          // Ignore keep-alive or malformed frames.
        }
      };

      source.onerror = () => {
        closeCurrentSource?.();
        closeCurrentSource = undefined;
        if (cancelled) return;
        void loadTimeline(currentSessionId, () => !cancelled);
        reconnectId = window.setTimeout(() => {
          if (!cancelled) connect();
        }, backoffMs);
        backoffMs = Math.min(backoffMs * 2, SSE_BACKOFF_MAX_MS);
      };
    }

    connect();

    return () => {
      cancelled = true;
      closeCurrentSource?.();
      if (pollId !== undefined) window.clearInterval(pollId);
      if (reconnectId !== undefined) window.clearTimeout(reconnectId);
    };
  }, [sessionId, invalidateRelatedQueries, loadTimeline]);

  const resetTimeline = useCallback(() => {
    setEvents([]);
    setError(null);
  }, []);

  return { error, events, loading, refreshTimeline, resetTimeline };
}
```

- [ ] **Step 4: Remove center-pane fallback calls to `api.getTimeline`**

Keep `api.getTimeline` in `apps/web/src/api.ts` for compatibility, but `useTimeline` must not import or call it. Confirm with:

```powershell
rg -n "getTimeline|projectAcpEventsToTimelineEvents|mergeProjectedAcpEvent" apps/web/src/shell/state apps/web/src/shell/panes apps/web/src/shell/acp
```

Expected: no matches in ACP center-pane state or panes.

- [ ] **Step 5: Run focused tests**

Run:

```powershell
cd apps/web
npm run test:unit -- --run src/shell/acp/__tests__/acpEvents.test.ts src/shell/state/__tests__/useTimeline.test.tsx src/shell/__tests__/useTimeline.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/web/src/shell/state/useTimeline.ts apps/web/src/shell/state/__tests__/useTimeline.test.tsx apps/web/src/shell/__tests__/useTimeline.test.tsx
git commit -m "feat(web): make timeline state acp native"
```

## Task 3: Build ACP Interaction Surface And Renderer

Task 3 and Task 4 are a tight pair. Task 3 introduces the surface and renderer;
Task 4 immediately supplies the composer needed for the surface tests to pass.
Do not stop for final verification between these two tasks; run the Task 4
verification before committing both tasks if executing inline. If using
subagents, assign both tasks to the same worker because they share the new
`apps/web/src/shell/acp` package.

**Files:**
- Create: `apps/web/src/shell/acp/AcpRenderSlots.tsx`
- Create: `apps/web/src/shell/acp/AcpEventRenderer.tsx`
- Create: `apps/web/src/shell/acp/AcpInteractionSurface.tsx`
- Test: `apps/web/src/shell/acp/__tests__/AcpInteractionSurface.test.tsx`

- [ ] **Step 1: Write failing surface tests**

Create `apps/web/src/shell/acp/__tests__/AcpInteractionSurface.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { AcpEvent } from "../../../types";
import { AcpInteractionSurface } from "../AcpInteractionSurface";

function acp(overrides: Partial<AcpEvent> & Pick<AcpEvent, "id" | "sequence" | "event_type">): AcpEvent {
  return {
    session_id: "session-1",
    payload: {},
    projection: {},
    created_at: "2026-05-15T00:00:00Z",
    ...overrides,
  };
}

const baseProps = {
  sessionId: "session-1",
  taskId: "task-1",
  emptyMessage: null,
  loading: false,
  running: false,
  error: null,
  queuedComposerDraft: null,
  onQueuedComposerDraftHandled: vi.fn(),
  onSendMessage: vi.fn(),
  onCancel: vi.fn(),
  onReloadInput: vi.fn(),
  onOpenPath: vi.fn(),
  onApproved: vi.fn(),
};

describe("AcpInteractionSurface", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  it("renders ACP user, assistant, tool, file, status, and unknown events", () => {
    render(
      <AcpInteractionSurface
        {...baseProps}
        events={[
          acp({ id: "u", sequence: 1, event_type: "docagent/prompt", payload: { prompt: "Write a PRD" } }),
          acp({ id: "a", sequence: 2, event_type: "message_delta", payload: { role: "assistant", content: "Working" } }),
          acp({ id: "t", sequence: 3, event_type: "tool/call", payload: { name: "read_file", status: "running" } }),
          acp({ id: "f", sequence: 4, event_type: "file/write", payload: { path: "draft/draft.md" } }),
          acp({ id: "s", sequence: 5, event_type: "session/completed", payload: {} }),
          acp({ id: "x", sequence: 6, event_type: "vendor/custom", payload: { hello: "world" } }),
        ]}
      />,
    );

    expect(screen.getByText("Write a PRD")).toBeInTheDocument();
    expect(screen.getByText("Working")).toBeInTheDocument();
    expect(screen.getByText(/read_file/i)).toBeInTheDocument();
    expect(screen.getByText(/draft\/draft\.md/i)).toBeInTheDocument();
    expect(screen.getByText(/Session status/i)).toBeInTheDocument();
    expect(screen.getByText(/vendor\/custom/i)).toBeInTheDocument();
  });

  it("copies event text without assistant-ui actions", async () => {
    const user = userEvent.setup();
    render(
      <AcpInteractionSurface
        {...baseProps}
        events={[acp({ id: "a", sequence: 1, event_type: "message_delta", payload: { content: "Copy me" } })]}
      />,
    );

    await user.click(screen.getByRole("button", { name: /copy/i }));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("Copy me");
  });

  it("requests reload from the selected event id", async () => {
    const user = userEvent.setup();
    const onReloadInput = vi.fn();
    render(
      <AcpInteractionSurface
        {...baseProps}
        onReloadInput={onReloadInput}
        events={[
          acp({ id: "u", sequence: 1, event_type: "docagent/prompt", payload: { prompt: "Original" } }),
          acp({ id: "a", sequence: 2, event_type: "message_delta", payload: { role: "assistant", content: "Answer" } }),
        ]}
      />,
    );

    await user.click(screen.getByRole("button", { name: /reload response/i }));
    expect(onReloadInput).toHaveBeenCalledWith("a");
  });
});
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
cd apps/web
npm run test:unit -- --run src/shell/acp/__tests__/AcpInteractionSurface.test.tsx
```

Expected: FAIL because the components do not exist.

- [ ] **Step 3: Implement render slots**

Create `apps/web/src/shell/acp/AcpRenderSlots.tsx`:

```tsx
import type { AcpEvent, TimelineEvent } from "../../types";
import { ApprovalCard } from "../conversation/cards/ApprovalCard";
import { ArtifactCard } from "../conversation/cards/ArtifactCard";
import { ChecklistCard } from "../conversation/cards/ChecklistCard";
import { OutlineCard } from "../conversation/cards/OutlineCard";

interface AcpRenderSlotsProps {
  event: AcpEvent;
  sessionId: string | null;
  taskId: string | null;
  onApproved: () => Promise<void>;
  onOpenPath: (path: string) => Promise<void>;
}

export function AcpRenderSlot({
  event,
  onApproved,
  onOpenPath,
  sessionId,
  taskId,
}: AcpRenderSlotsProps) {
  const timelineKind = typeof event.projection.timeline_kind === "string" ? event.projection.timeline_kind : "";
  const timelineEvent = toTimelineEvent(event, taskId, timelineKind);

  if (timelineKind === "propose_outline") {
    return <OutlineCard event={timelineEvent} sessionId={sessionId} taskId={taskId} onApproved={onApproved} onOpenPath={onOpenPath} />;
  }
  if (timelineKind === "run_checklist") {
    return <ChecklistCard event={timelineEvent} onOpenPath={onOpenPath} />;
  }
  if (timelineKind === "export_markdown" || timelineKind === "export_docx" || timelineKind === "export_pdf") {
    return <ArtifactCard event={timelineEvent} onOpenPath={onOpenPath} />;
  }
  if (timelineKind === "approval_requested") {
    return <ApprovalCard event={timelineEvent} />;
  }
  return null;
}

export function hasAcpRenderSlot(event: AcpEvent): boolean {
  const timelineKind = typeof event.projection.timeline_kind === "string" ? event.projection.timeline_kind : "";
  return ["propose_outline", "run_checklist", "export_markdown", "export_docx", "export_pdf", "approval_requested"].includes(timelineKind);
}

function toTimelineEvent(event: AcpEvent, taskId: string | null, timelineKind: string): TimelineEvent {
  return {
    id: typeof event.projection.timeline_id === "string" ? event.projection.timeline_id : event.id,
    session_id: event.session_id,
    task_id: taskId ?? "",
    actor: typeof event.projection.actor === "string" ? event.projection.actor : "agent",
    kind: timelineKind || event.event_type,
    raw_event_id: event.id,
    summary: typeof event.projection.summary === "string" ? event.projection.summary : event.event_type,
    paths: Array.isArray(event.projection.paths)
      ? event.projection.paths.filter((path): path is string => typeof path === "string")
      : [],
    status: typeof event.projection.status === "string" ? event.projection.status : "succeeded",
    created_at: event.created_at,
  };
}
```

- [ ] **Step 4: Implement ACP event renderer**

Create `apps/web/src/shell/acp/AcpEventRenderer.tsx`:

```tsx
import { Copy, RefreshCcw } from "lucide-react";
import type { AcpEvent } from "../../types";
import { classifyAcpEvent, textFromAcpEvent } from "./acpEvents";
import { AcpRenderSlot, hasAcpRenderSlot } from "./AcpRenderSlots";

interface AcpEventRendererProps {
  event: AcpEvent;
  sessionId: string | null;
  taskId: string | null;
  onApproved: () => Promise<void>;
  onCopy: (event: AcpEvent) => Promise<void>;
  onOpenPath: (path: string) => Promise<void>;
  onReloadInput: (eventId: string) => Promise<void>;
}

export function AcpEventRenderer({
  event,
  onApproved,
  onCopy,
  onOpenPath,
  onReloadInput,
  sessionId,
  taskId,
}: AcpEventRendererProps) {
  const classified = classifyAcpEvent(event);
  const text = textFromAcpEvent(event);
  const isAssistantMessage = classified.family === "message" && classified.role === "assistant";
  const alignment = classified.role === "user" ? "user" : "assistant";

  if (hasAcpRenderSlot(event)) {
    return (
      <article className="acp-event acp-event--card" data-family={classified.family}>
        <AcpRenderSlot event={event} sessionId={sessionId} taskId={taskId} onApproved={onApproved} onOpenPath={onOpenPath} />
      </article>
    );
  }

  return (
    <article className={`acp-event acp-event--${alignment}`} data-family={classified.family} data-status={classified.status}>
      <div className="acp-event__body">
        {classified.family === "message" ? (
          <p className="acp-event__text">{text}</p>
        ) : (
          <>
            <header className="acp-event__header">
              <strong>{classified.title}</strong>
              <span>{classified.status}</span>
            </header>
            {text && <p className="acp-event__text">{text}</p>}
            {classified.paths.length > 0 && (
              <button type="button" className="acp-event__path" onClick={() => onOpenPath(classified.paths[0])}>
                {classified.paths.join(", ")}
              </button>
            )}
            {classified.family === "unknown" && (
              <pre className="acp-event__payload">{JSON.stringify(event.payload, null, 2)}</pre>
            )}
          </>
        )}
      </div>
      <div className="acp-event__actions">
        {text && (
          <button type="button" className="acp-icon-button" aria-label="Copy text" onClick={() => onCopy(event)}>
            <Copy size={14} />
          </button>
        )}
        {isAssistantMessage && (
          <button type="button" className="acp-icon-button" aria-label="Reload response" onClick={() => onReloadInput(event.id)}>
            <RefreshCcw size={14} />
          </button>
        )}
      </div>
    </article>
  );
}
```

- [ ] **Step 5: Implement ACP interaction surface**

Create `apps/web/src/shell/acp/AcpInteractionSurface.tsx`:

```tsx
import type { AcpEvent, MessageAttachment } from "../../types";
import { mergeAcpEvents, textFromAcpEvent } from "./acpEvents";
import { AcpComposer } from "./AcpComposer";
import { AcpEventRenderer } from "./AcpEventRenderer";

export interface AcpInteractionSurfaceProps {
  sessionId: string | null;
  taskId: string | null;
  events: AcpEvent[];
  emptyMessage: string | null;
  loading: boolean;
  running: boolean;
  error: string | null;
  queuedComposerDraft?: string | null;
  onApproved: () => Promise<void>;
  onCancel: () => Promise<void>;
  onOpenPath: (path: string) => Promise<void>;
  onQueuedComposerDraftHandled?: () => void;
  onReloadInput: (eventId: string | null) => Promise<void>;
  onSendMessage: (input: string, attachments?: MessageAttachment[]) => Promise<void>;
}

export function AcpInteractionSurface({
  emptyMessage,
  error,
  events,
  loading,
  onApproved,
  onCancel,
  onOpenPath,
  onQueuedComposerDraftHandled,
  onReloadInput,
  onSendMessage,
  queuedComposerDraft,
  running,
  sessionId,
  taskId,
}: AcpInteractionSurfaceProps) {
  const mergedEvents = mergeAcpEvents(events);

  async function copyEvent(event: AcpEvent) {
    await navigator.clipboard?.writeText(textFromAcpEvent(event));
  }

  return (
    <section className="acp-surface">
      <div className="acp-thread">
        {emptyMessage && mergedEvents.length === 0 && <div className="conversation-empty">{emptyMessage}</div>}
        {mergedEvents.map((event) => (
          <AcpEventRenderer
            key={event.id}
            event={event}
            sessionId={sessionId}
            taskId={taskId}
            onApproved={onApproved}
            onCopy={copyEvent}
            onOpenPath={onOpenPath}
            onReloadInput={onReloadInput}
          />
        ))}
        {(loading || running) && (
          <div className="acp-thread-status" role="status">
            {running ? "Agent is working..." : "Refreshing events..."}
          </div>
        )}
      </div>
      <AcpComposer
        disabled={!taskId}
        draftText={queuedComposerDraft}
        isRunning={running}
        onCancel={onCancel}
        onDraftTextApplied={onQueuedComposerDraftHandled}
        onSend={onSendMessage}
      />
      {error && <p className="pane-note pane-note--error">{error}</p>}
    </section>
  );
}
```

- [ ] **Step 6: Run tests**

Run:

```powershell
cd apps/web
npm run test:unit -- --run src/shell/acp/__tests__/AcpInteractionSurface.test.tsx src/shell/acp/__tests__/acpEvents.test.ts
```

Expected: FAIL because `AcpComposer` does not exist yet. This is an expected
temporary failure and is resolved by Task 4 immediately after this task.

- [ ] **Step 7: Commit**

```powershell
git add apps/web/src/shell/acp/AcpRenderSlots.tsx apps/web/src/shell/acp/AcpEventRenderer.tsx apps/web/src/shell/acp/AcpInteractionSurface.tsx apps/web/src/shell/acp/__tests__/AcpInteractionSurface.test.tsx
git commit -m "feat(web): add acp interaction surface"
```

## Task 4: Build Local ACP Composer

**Files:**
- Create: `apps/web/src/shell/acp/AcpComposer.tsx`
- Test: `apps/web/src/shell/acp/__tests__/AcpComposer.test.tsx`
- Reuse: `apps/web/src/shell/assistant/DocAgentSlashCommands.tsx` until assistant package deletion, then move it if needed.

- [ ] **Step 1: Write failing composer tests**

Create `apps/web/src/shell/acp/__tests__/AcpComposer.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AcpComposer } from "../AcpComposer";

describe("AcpComposer", () => {
  it("sends text input on click", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn().mockResolvedValue(undefined);
    render(<AcpComposer disabled={false} isRunning={false} onCancel={vi.fn()} onSend={onSend} />);

    await user.type(screen.getByLabelText("Message"), "Draft this");
    await user.click(screen.getByRole("button", { name: /send message/i }));

    expect(onSend).toHaveBeenCalledWith("Draft this", []);
  });

  it("applies queued draft text and notifies caller", async () => {
    const onDraftTextApplied = vi.fn();
    render(
      <AcpComposer
        disabled={false}
        draftText="Revise selection"
        isRunning={false}
        onCancel={vi.fn()}
        onDraftTextApplied={onDraftTextApplied}
        onSend={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("Message")).toHaveValue("Revise selection");
    expect(onDraftTextApplied).toHaveBeenCalled();
  });

  it("calls cancel when running", async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    render(<AcpComposer disabled={false} isRunning onCancel={onCancel} onSend={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: /stop the running agent/i }));
    expect(onCancel).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
cd apps/web
npm run test:unit -- --run src/shell/acp/__tests__/AcpComposer.test.tsx
```

Expected: FAIL because `AcpComposer.tsx` does not exist.

- [ ] **Step 3: Implement composer**

Create `apps/web/src/shell/acp/AcpComposer.tsx`:

```tsx
import { Paperclip, Send, Square, X } from "lucide-react";
import { ChangeEvent, KeyboardEvent, useEffect, useRef, useState } from "react";
import type { MessageAttachment } from "../../types";
import { DocAgentSlashCommands } from "../assistant/DocAgentSlashCommands";

interface AcpComposerProps {
  disabled: boolean;
  draftText?: string | null;
  isRunning?: boolean;
  onCancel?: () => void;
  onDraftTextApplied?: () => void;
  onSend: (input: string, attachments?: MessageAttachment[]) => Promise<void>;
}

export function AcpComposer({
  disabled,
  draftText,
  isRunning = false,
  onCancel,
  onDraftTextApplied,
  onSend,
}: AcpComposerProps) {
  const [text, setText] = useState("");
  const [attachments, setAttachments] = useState<MessageAttachment[]>([]);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!draftText) return;
    setText(draftText);
    inputRef.current?.focus();
    onDraftTextApplied?.();
  }, [draftText, onDraftTextApplied]);

  function selectCommand(command: string) {
    setText(`${command} `);
    inputRef.current?.focus();
  }

  async function submit() {
    const input = text.trimEnd();
    if (!input || disabled || isRunning) return;
    const nextAttachments = attachments;
    setText("");
    setAttachments([]);
    await onSend(input, nextAttachments);
  }

  function keyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submit();
    }
  }

  function addLocalAttachments(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    setAttachments((current) => [
      ...current,
      ...files.map((file) => ({
        name: file.name,
        markdown_path: `inputs/markdown/${file.name}.md`,
        source_path: `inputs/original/${file.name}`,
      })),
    ]);
    event.target.value = "";
  }

  return (
    <div className="acp-composer" aria-disabled={disabled}>
      <div className="acp-composer__input-wrap">
        {attachments.length > 0 && (
          <div className="acp-composer__attachments">
            {attachments.map((attachment) => (
              <span className="acp-attachment-chip" key={`${attachment.name}-${attachment.markdown_path}`}>
                <span>{attachment.name}</span>
                <button
                  type="button"
                  aria-label={`Remove ${attachment.name}`}
                  onClick={() => setAttachments((current) => current.filter((item) => item !== attachment))}
                >
                  <X size={12} />
                </button>
              </span>
            ))}
          </div>
        )}
        <textarea
          ref={inputRef}
          aria-label="Message"
          disabled={disabled}
          placeholder={isRunning ? "Agent is working" : "Message the agent, or type / for commands"}
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={keyDown}
        />
        <DocAgentSlashCommands query={text} onSelect={selectCommand} />
      </div>
      <input ref={fileInputRef} className="sr-only" type="file" multiple onChange={addLocalAttachments} />
      <button
        type="button"
        className="acp-attach-button"
        disabled={disabled}
        aria-label="Attach file"
        onClick={() => fileInputRef.current?.click()}
      >
        <Paperclip size={15} />
      </button>
      {isRunning ? (
        <button type="button" className="acp-send-button acp-send-button--stop" aria-label="Stop the running agent" onClick={() => onCancel?.()}>
          <Square size={13} />
        </button>
      ) : (
        <button type="button" className="acp-send-button" aria-label="Send message" disabled={disabled} onClick={() => void submit()}>
          <Send size={15} />
        </button>
      )}
    </div>
  );
}
```

After assistant package deletion, move `DocAgentSlashCommands.tsx` into `apps/web/src/shell/acp/DocAgentSlashCommands.tsx` and update the import.

- [ ] **Step 4: Run composer and surface tests**

Run:

```powershell
cd apps/web
npm run test:unit -- --run src/shell/acp/__tests__/AcpComposer.test.tsx src/shell/acp/__tests__/AcpInteractionSurface.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/web/src/shell/acp/AcpComposer.tsx apps/web/src/shell/acp/__tests__/AcpComposer.test.tsx
git commit -m "feat(web): add acp composer"
```

## Task 5: Integrate ACP Surface Into ConversationPane

**Files:**
- Modify: `apps/web/src/shell/panes/ConversationPane.tsx`
- Modify: `apps/web/src/shell/panes/__tests__/ConversationPane.test.tsx`
- Modify: `apps/web/src/shell/panes/__tests__/inputForReload.test.ts`
- Modify: `apps/web/src/shell/AppShell.tsx`
- Modify: `apps/web/src/shell/__tests__/AppShell.test.tsx`

- [ ] **Step 1: Update ConversationPane tests to assert ACP surface behavior**

In `apps/web/src/shell/panes/__tests__/ConversationPane.test.tsx`, replace assistant-ui wrapper expectations with:

```tsx
it("renders the center pane through the ACP interaction surface", () => {
  render(
    <ConversationPane
      activeSession={session}
      activeTask={task}
      createSession={vi.fn()}
      ensureSession={vi.fn()}
      events={[
        {
          id: "acp-1",
          session_id: session.id,
          sequence: 1,
          event_type: "docagent/prompt",
          payload: { prompt: "Hello" },
          projection: {},
          created_at: "2026-05-15T00:00:00Z",
        },
      ]}
      error={null}
      loading={false}
      onOpenPath={vi.fn()}
      refreshTimeline={vi.fn()}
      refreshWorkspace={vi.fn()}
    />,
  );

  expect(screen.getByText("Hello")).toBeInTheDocument();
  expect(screen.queryByTestId("assistant-runtime-provider")).not.toBeInTheDocument();
});
```

In `inputForReload.test.ts`, switch fixtures from `TimelineEvent[]` to `AcpEvent[]` and import `findReloadInput` from `../acp/acpEvents` or keep a local `inputForReload` wrapper that delegates to ACP helpers.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
cd apps/web
npm run test:unit -- --run src/shell/panes/__tests__/ConversationPane.test.tsx src/shell/panes/__tests__/inputForReload.test.ts
```

Expected: FAIL because `ConversationPane` still imports assistant-ui runtime pieces and accepts `TimelineEvent[]`.

- [ ] **Step 3: Refactor `ConversationPane` to use ACP surface**

Update `apps/web/src/shell/panes/ConversationPane.tsx`:

- Remove `StartRunConfig`, `AssistantRuntimeProvider`, `DocAgentComposer`, `DocAgentThread`, and `useDocAgentAssistantRuntime` imports.
- Change `events: TimelineEvent[]` to `events: AcpEvent[]`.
- Import `AcpInteractionSurface` and `findReloadInput`.
- Replace the `<AssistantRuntimeProvider>` block with:

```tsx
<AcpInteractionSurface
  sessionId={activeSession?.id ?? null}
  taskId={activeTask?.id ?? null}
  events={events}
  emptyMessage={emptyMessage(activeTask, activeSession)}
  loading={loading}
  running={isRunning}
  error={error}
  queuedComposerDraft={queuedComposerDraft}
  onApproved={async () => {
    await refreshWorkspace();
    await refreshTimeline();
  }}
  onCancel={cancelActiveSession}
  onOpenPath={onOpenPath}
  onQueuedComposerDraftHandled={onQueuedComposerDraftHandled}
  onReloadInput={reloadInput}
  onSendMessage={submitOrCancel}
/>
```

Change reload implementation to:

```ts
const reloadInput = useCallback(
  async (parentEventId: string | null) => {
    const input = findReloadInput(eventsRef.current, parentEventId);
    if (!input) {
      setStatus("No previous user message to reload.");
      return;
    }
    await submitOrCancel(input);
  },
  [submitOrCancel],
);
```

Remove exported `inputForReload` if tests now cover `findReloadInput`.

- [ ] **Step 4: Update `AppShell` types if needed**

`AppShell` should pass `timeline.events` as `AcpEvent[]` without projection. If TypeScript errors remain, update prop types to match `AcpEvent[]`.

- [ ] **Step 5: Run focused frontend tests**

Run:

```powershell
cd apps/web
npm run test:unit -- --run src/shell/acp/__tests__/acpEvents.test.ts src/shell/acp/__tests__/AcpInteractionSurface.test.tsx src/shell/acp/__tests__/AcpComposer.test.tsx src/shell/panes/__tests__/ConversationPane.test.tsx src/shell/__tests__/AppShell.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/web/src/shell/panes/ConversationPane.tsx apps/web/src/shell/panes/__tests__/ConversationPane.test.tsx apps/web/src/shell/panes/__tests__/inputForReload.test.ts apps/web/src/shell/AppShell.tsx apps/web/src/shell/__tests__/AppShell.test.tsx
git commit -m "feat(web): wire conversation pane to acp surface"
```

## Task 6: Replace Assistant UI Styling And Remove Assistant Runtime Code

**Files:**
- Move/Modify: `apps/web/src/shell/theme/assistant-ui.css` to `apps/web/src/shell/theme/acp.css`
- Modify: stylesheet import site, likely `apps/web/src/main.tsx`
- Move if needed: `apps/web/src/shell/assistant/DocAgentSlashCommands.tsx` to `apps/web/src/shell/acp/DocAgentSlashCommands.tsx`
- Delete: `apps/web/src/shell/assistant/docAgentAssistantMessages.ts`
- Delete: `apps/web/src/shell/assistant/DocAgentThread.tsx`
- Delete: `apps/web/src/shell/assistant/DocAgentComposer.tsx`
- Delete: `apps/web/src/shell/assistant/DocAgentMessageParts.tsx`
- Delete: `apps/web/src/shell/assistant/useDocAgentAssistantRuntime.ts`
- Delete assistant-ui-specific tests that no longer apply.
- Modify: `apps/web/package.json`

- [ ] **Step 1: Add guard test that no center-pane code imports assistant-ui**

Create or update a test in `apps/web/src/shell/acp/__tests__/noAssistantUiImports.test.ts`:

```ts
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const root = join(process.cwd(), "src", "shell");

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry);
    if (path.includes(`${join("shell", "assistant")}`)) return [];
    return statSync(path).isDirectory() ? files(path) : [path];
  });
}

it("does not import assistant-ui outside removed compatibility code", () => {
  const offenders = files(root).filter((path) => readFileSync(path, "utf8").includes("@assistant-ui/"));
  expect(offenders).toEqual([]);
});
```

- [ ] **Step 2: Run guard test and verify it fails**

Run:

```powershell
cd apps/web
npm run test:unit -- --run src/shell/acp/__tests__/noAssistantUiImports.test.ts
```

Expected: FAIL while assistant-ui imports still exist outside deleted compatibility code.

- [ ] **Step 3: Rename CSS classes**

Move the file:

```powershell
Move-Item apps/web/src/shell/theme/assistant-ui.css apps/web/src/shell/theme/acp.css
```

In `acp.css`, replace `.aui-` class prefixes with `.acp-` equivalents used by the new components. Keep shared tokens and dimensions. Update the stylesheet import from `assistant-ui.css` to `acp.css`.

- [ ] **Step 4: Move slash command component**

If `DocAgentSlashCommands.tsx` is the only remaining useful file in `apps/web/src/shell/assistant`, move it:

```powershell
Move-Item apps/web/src/shell/assistant/DocAgentSlashCommands.tsx apps/web/src/shell/acp/DocAgentSlashCommands.tsx
```

Update `AcpComposer.tsx` import:

```ts
import { DocAgentSlashCommands } from "./DocAgentSlashCommands";
```

- [ ] **Step 5: Delete assistant-ui runtime files and tests**

Remove assistant-ui-specific files only after grep shows no production imports:

```powershell
rg -n "@assistant-ui|DocAgentThread|DocAgentComposer|useDocAgentAssistantRuntime|docAgentAssistantMessages" apps/web/src apps/web/tests
```

Delete files reported only as obsolete assistant-ui code or tests. Keep product card components under `apps/web/src/shell/conversation/cards`.

- [ ] **Step 6: Remove dependencies**

Edit `apps/web/package.json` and remove:

```json
"@assistant-ui/react": "0.14.5"
```

and any `@assistant-ui/core` entry if present. Then run:

```powershell
cd apps/web
npm install
```

Expected: lockfile updates and no install error.

- [ ] **Step 7: Run grep and focused tests**

Run:

```powershell
rg -n "@assistant-ui|assistant-ui" apps/web/src apps/web/package.json apps/web/package-lock.json
cd apps/web
npm run test:unit -- --run src/shell/acp/__tests__/noAssistantUiImports.test.ts src/shell/acp/__tests__/AcpInteractionSurface.test.tsx src/shell/acp/__tests__/AcpComposer.test.tsx
```

Expected: `rg` returns no assistant-ui references in source or package files; tests pass.

- [ ] **Step 8: Commit**

```powershell
git add apps/web
git commit -m "refactor(web): remove assistant-ui center runtime"
```

## Task 7: Backend ACP Event Store Guards

**Files:**
- Modify: `services/api/tests/test_acp_events.py`
- Modify: `services/api/tests/test_phase3_api.py`
- Modify: `services/api/docagent_api/routes/_shared.py`
- Modify: `services/api/docagent_api/routes/sessions.py`

- [ ] **Step 1: Add tests for ACP event source and session scoping**

Add to `services/api/tests/test_acp_events.py`:

```py
def test_prompt_records_user_prompt_without_requiring_timeline_projection(client) -> None:
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Use ACP"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    response = client.post(f"/sessions/{session['id']}/messages", json={"message": "Hello"}, params={"background": False})
    assert response.status_code == 200

    acp_events = client.get(f"/sessions/{session['id']}/events").json()
    assert any(event["event_type"] == "docagent/prompt" and event["payload"]["prompt"] == "Hello" for event in acp_events)


def test_acp_events_are_session_scoped(client) -> None:
    task_one = client.post("/tasks", json={"doc_type_id": "prd", "brief": "One"}).json()
    task_two = client.post("/tasks", json={"doc_type_id": "prd", "brief": "Two"}).json()
    session_one = client.post(f"/tasks/{task_one['id']}/sessions").json()
    session_two = client.post(f"/tasks/{task_two['id']}/sessions").json()

    client.post(f"/sessions/{session_one['id']}/messages", json={"message": "Only one"})

    events_one = client.get(f"/sessions/{session_one['id']}/events").json()
    events_two = client.get(f"/sessions/{session_two['id']}/events").json()

    assert any(event["payload"].get("prompt") == "Only one" for event in events_one)
    assert all(event["payload"].get("prompt") != "Only one" for event in events_two)
```

Add to `services/api/tests/test_phase3_api.py`:

```py
def test_authoring_events_endpoint_contains_runtime_failure_before_timeline_compat(client, monkeypatch) -> None:
    class FailingAdapter:
        def create_session(self, session_id, prompt_bundle):
            from docagent_contracts import RuntimeOperationResult, RuntimeSessionState
            return RuntimeOperationResult(session_id=session_id, next_state=RuntimeSessionState.IDLE)

        def send_prompt(self, session_id, prompt, metadata=None):
            raise RuntimeError("runtime unavailable")

    monkeypatch.setattr("docagent_api.app.create_runtime_adapter", lambda: FailingAdapter())
    task = client.post("/tasks", json={"doc_type_id": "prd", "brief": "fail"}).json()
    session = client.post(f"/tasks/{task['id']}/sessions").json()

    client.post(f"/sessions/{session['id']}/messages", json={"message": "Run"}, params={"background": True})

    events = client.get(f"/sessions/{session['id']}/events").json()
    assert any(event["event_type"] in {"runtime/error", "docagent/projection"} for event in events)
```

- [ ] **Step 2: Run backend tests and verify failures**

Run:

```powershell
.venv\Scripts\python.exe -m pytest services/api/tests/test_acp_events.py services/api/tests/test_phase3_api.py -q --basetemp=.local/pytest-tmp-acp-guards
```

Expected: At least one new test fails if failure/status events still rely only on semantic timeline projection or if monkeypatch target needs adjustment.

- [ ] **Step 3: Add explicit ACP append helpers**

In `services/api/docagent_api/routes/_shared.py`, add helpers:

```py
def append_acp_status_event(
    state: DocAgentState,
    session_id: str,
    status: RuntimeSessionState,
    summary: str | None = None,
) -> None:
    state.append_acp_event(
        session_id,
        {
            "method": f"session/{status.value}",
            "status": status.value,
            "message": summary or f"Session status changed to {status.value}",
        },
    )


def append_acp_error_event(
    state: DocAgentState,
    session_id: str,
    message: str,
) -> None:
    state.append_acp_event(
        session_id,
        {
            "method": "runtime/error",
            "message": message,
        },
    )
```

Call `append_acp_status_event` in `set_session_state` before or after compatibility timeline append. Call `append_acp_error_event` in background failure paths and worker failure paths before compatibility timeline append.

- [ ] **Step 4: Keep `/timeline` compatibility but stop using it as authoring source**

In `sessions.py`, keep `/timeline` endpoints but add comments and tests indicating compatibility only. Do not remove the endpoint in this task.

- [ ] **Step 5: Run focused backend tests**

Run:

```powershell
.venv\Scripts\python.exe -m pytest services/api/tests/test_acp_events.py services/api/tests/test_phase3_api.py services/api/tests/test_worker_tasks.py -q --basetemp=.local/pytest-tmp-acp-guards
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add services/api/docagent_api/routes/_shared.py services/api/docagent_api/routes/sessions.py services/api/tests/test_acp_events.py services/api/tests/test_phase3_api.py services/api/tests/test_worker_tasks.py
git commit -m "test(api): guard acp event source"
```

## Task 8: Expand Mock ACP Runtime Coverage

**Files:**
- Modify: `agent/runtime-adapters/mock/docagent_mock_runtime/adapter.py`
- Modify: `agent/runtime-adapters/mock/tests`
- Modify: `packages/contracts/tests/test_runtime_contracts.py`

- [ ] **Step 1: Add mock runtime ACP family tests**

Replace `test_mock_runtime_send_prompt_returns_acp_updates` in
`agent/runtime-adapters/mock/tests/test_adapter.py` with:

```py
def test_mock_runtime_send_prompt_emits_required_acp_event_families(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "brief.md").write_text("Create a pricing PRD\n", encoding="utf-8")

    adapter = MockRuntimeAdapter()
    adapter.create_session("session-001", _prompt_bundle(workspace))

    result = adapter.send_prompt("session-001", "Build context", {"action": "start_loop"})
    event_types = [update.event_type for update in result.acp_updates]

    assert any("message" in event_type for event_type in event_types)
    assert any("tool" in event_type for event_type in event_types)
    assert any("file" in event_type for event_type in event_types)
    assert any("permission" in event_type or "approval" in event_type for event_type in event_types)
    assert all(update.payload for update in result.acp_updates)
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
.venv\Scripts\python.exe -m pytest agent/runtime-adapters/mock/tests -q --basetemp=.local/pytest-tmp-mock-acp
```

Expected: FAIL because mock `send_prompt` currently emits only message updates.

- [ ] **Step 3: Implement richer mock ACP updates**

In `MockRuntimeAdapter.send_prompt`, convert semantic events from `_run_prompt_action` into ACP updates:

```py
def _acp_updates_for_events(self, session_id: str, prompt: str, events: list[SemanticTimelineEvent]) -> list[AcpRuntimeUpdate]:
    updates = [
        AcpRuntimeUpdate(
            session_id=session_id,
            event_type="message_delta",
            payload={"role": "assistant", "content": prompt, "message_id": f"{session_id}-mock-message"},
        ),
        AcpRuntimeUpdate(
            session_id=session_id,
            event_type="message_completed",
            payload={"role": "assistant", "message_id": f"{session_id}-mock-message"},
        ),
    ]
    for event in events:
        event_type = _acp_event_type_for_semantic(event)
        updates.append(
            AcpRuntimeUpdate(
                session_id=session_id,
                event_type=event_type,
                payload={
                    "id": event.id,
                    "summary": event.summary,
                    "paths": event.paths,
                    "status": event.status.value,
                },
                projection={
                    "timeline_id": event.id,
                    "timeline_kind": event.kind.value,
                    "actor": event.actor.value,
                    "summary": event.summary,
                    "paths": event.paths,
                    "status": event.status.value,
                },
            )
        )
    return updates
```

Add helper:

```py
def _acp_event_type_for_semantic(event: SemanticTimelineEvent) -> str:
    if event.kind is SemanticEventKind.APPROVAL_REQUESTED:
        return "permission/request"
    if event.paths:
        return "file/write"
    if event.actor is TimelineActor.SYSTEM:
        return "session/status"
    return "tool/result"
```

Use it in `send_prompt`:

```py
result = self._run_prompt_action(session_id, prompt, metadata or {})
return RuntimeOperationResult(
    session_id=session_id,
    next_state=result.next_state,
    events=result.events,
    changed_paths=result.changed_paths,
    raw_events=result.raw_events,
    acp_updates=self._acp_updates_for_events(session_id, prompt, result.events),
)
```

- [ ] **Step 4: Run mock and contract tests**

Run:

```powershell
.venv\Scripts\python.exe -m pytest agent/runtime-adapters/mock/tests packages/contracts/tests/test_runtime_contracts.py -q --basetemp=.local/pytest-tmp-mock-acp
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add agent/runtime-adapters/mock packages/contracts/tests/test_runtime_contracts.py
git commit -m "feat(runtime): expand mock acp updates"
```

## Task 9: Tighten OpenHands ACP Shim Boundary

**Files:**
- Modify: `agent/runtime-adapters/openhands/docagent_openhands_runtime/adapter.py`
- Modify: `agent/runtime-adapters/openhands/docagent_openhands_runtime/client.py`
- Modify: `agent/runtime-adapters/openhands/tests`

- [ ] **Step 1: Add OpenHands adapter tests for raw preservation and ACP updates**

Add to `agent/runtime-adapters/openhands/tests/test_openhands_adapter.py`:

```py
class MixedPayloadOpenHandsClient(FakeOpenHandsClient):
    def send_message(self, runtime_session_id: str, message: str) -> list[dict[str, Any]]:
        self.messages.append(message)
        return [
            {"kind": "agent_message", "id": "m1", "content": "Hello"},
            {"kind": "file_written", "path": "draft/draft.md", "content": "Draft"},
            {"kind": "strange_event", "value": 42},
        ]


def test_send_prompt_returns_acp_updates_and_preserves_raw_payload(tmp_path: Path) -> None:
    client = MixedPayloadOpenHandsClient()
    adapter = OpenHandsRuntimeAdapter(client)
    adapter.create_session("session-001", _prompt_bundle(tmp_path))

    result = adapter.send_prompt("session-001", "Write", {"action": "send_message"})

    assert [update.event_type for update in result.acp_updates] == [
        "openhands/session_created",
        "message_delta",
        "file/write",
        "openhands/strange_event",
    ]
    assert result.acp_updates[-1].payload["value"] == 42
```

- [ ] **Step 2: Run tests and verify failures**

Run:

```powershell
.venv\Scripts\python.exe -m pytest agent/runtime-adapters/openhands/tests -q --basetemp=.local/pytest-tmp-openhands-acp
```

Expected: FAIL if creation event type or unknown event handling differs.

- [ ] **Step 3: Normalize creation and unknown events**

In `map_openhands_payload_to_acp_update`, ensure:

```py
if kind == "session_created":
    return AcpRuntimeUpdate(
        session_id=session_id,
        event_type="openhands/session_created",
        payload=payload,
    )
```

Keep unknown events as:

```py
return AcpRuntimeUpdate(
    session_id=session_id,
    event_type=f"openhands/{kind}",
    payload=payload,
)
```

Do not add frontend-facing OpenHands-specific projections for unknown events.

- [ ] **Step 4: Document cross-process resume limitation in code comments only where the exception is raised**

In `client.py`, keep the existing explicit runtime error. If config names are changed in Task 10, keep backward-compatible `OPENHANDS_BASE_URL` fallback until docs and compose are updated.

- [ ] **Step 5: Run OpenHands adapter tests**

Run:

```powershell
.venv\Scripts\python.exe -m pytest agent/runtime-adapters/openhands/tests -q --basetemp=.local/pytest-tmp-openhands-acp
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add agent/runtime-adapters/openhands
git commit -m "refactor(runtime): tighten openhands acp shim"
```

## Task 10: Runtime Names And Deployment Configuration

**Files:**
- Modify: `services/api/docagent_api/runtime_factory.py`
- Modify: `docker-compose.override.yml`
- Modify: `.env.example`
- Modify: `scripts/dev.ps1`
- Modify: `tools/runtime/compose_smoke.py`
- Modify: `tests/test_litellm_compose.py`
- Modify: `tests/test_dev_entrypoint.py`
- Modify: docs listed in File Map.

- [ ] **Step 1: Add tests for canonical runtime names**

In `tests/test_dev_entrypoint.py`, update or add:

```py
def test_runtime_env_contract_uses_acp_runtime_names() -> None:
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    override = (ROOT / "docker-compose.override.yml").read_text(encoding="utf-8")

    assert "DOCAGENT_RUNTIME=mock-acp" in env_example
    assert "DOCAGENT_ACP_RUNTIME_URL=http://127.0.0.1:8001" in env_example
    assert "DOCAGENT_ACP_CONTAINER_RUNTIME_URL=http://openhands:8001" in env_example
    assert "OPENHANDS_CONTAINER_BASE_URL" not in env_example
    assert "DOCAGENT_ACP_RUNTIME_URL" in override
```

In a new or existing runtime factory test:

```py
def test_runtime_factory_accepts_acp_runtime_names(monkeypatch):
    from docagent_api.runtime_factory import create_runtime_adapter

    assert type(create_runtime_adapter("mock-acp")).__name__ == "MockRuntimeAdapter"
```

- [ ] **Step 2: Run tests and verify failures**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_dev_entrypoint.py tests/test_litellm_compose.py services/api/tests/test_runtime_factory.py -q --basetemp=.local/pytest-tmp-runtime-config
```

Expected: FAIL until canonical names and docs are updated. If `test_runtime_factory.py` does not exist, create it under `services/api/tests`.

- [ ] **Step 3: Update runtime factory aliases**

Modify `runtime_factory.py`:

```py
MOCK_RUNTIME_NAMES = {RuntimeKind.MOCK.value, "mock-acp"}
OPENHANDS_RUNTIME_NAMES = {RuntimeKind.OPENHANDS.value, "openhands-acp"}

def create_runtime_adapter(runtime_name: str | None = None) -> RuntimeAdapter:
    runtime = runtime_name or os.environ.get("DOCAGENT_RUNTIME", "mock-acp")
    if runtime in MOCK_RUNTIME_NAMES:
        from docagent_mock_runtime.adapter import MockRuntimeAdapter
        return MockRuntimeAdapter()
    if runtime in OPENHANDS_RUNTIME_NAMES:
        from docagent_openhands_runtime.adapter import OpenHandsRuntimeAdapter
        from docagent_openhands_runtime.client import OpenHandsAgentServerClient
        base_url = os.environ.get("DOCAGENT_ACP_RUNTIME_URL") or os.environ.get("OPENHANDS_BASE_URL")
        return OpenHandsRuntimeAdapter(OpenHandsAgentServerClient(base_url=base_url))
    raise RuntimeConfigurationError(f"Unsupported DOCAGENT_RUNTIME: {runtime}")
```

- [ ] **Step 4: Update compose and env docs**

Use these canonical names:

```text
DOCAGENT_RUNTIME=mock-acp
DOCAGENT_ACP_RUNTIME_URL=http://127.0.0.1:8001
DOCAGENT_ACP_CONTAINER_RUNTIME_URL=http://openhands:8001
LITELLM_BASE_URL=http://litellm:4000
```

In compose override, pass `DOCAGENT_ACP_RUNTIME_URL: ${DOCAGENT_ACP_CONTAINER_RUNTIME_URL:-http://openhands:8001}` to API and worker. Keep `OPENHANDS_BASE_URL` only if needed as a compatibility alias for the current client, and mark it compatibility in docs.

- [ ] **Step 5: Update dev script and smoke tests**

Update `scripts/dev.ps1` so `-Runtime openhands` sets `DOCAGENT_RUNTIME=openhands-acp`, and default runtime is `mock-acp`. Update compose smoke tests to use `mock-acp` and `openhands-acp`.

- [ ] **Step 6: Run config tests**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_dev_entrypoint.py tests/test_litellm_compose.py services/api/tests/test_runtime_factory.py -q --basetemp=.local/pytest-tmp-runtime-config
docker compose config
```

Expected: pytest PASS; `docker compose config` exit 0 and includes `DOCAGENT_RUNTIME: mock-acp` or the env-selected runtime.

- [ ] **Step 7: Commit**

```powershell
git add services/api/docagent_api/runtime_factory.py services/api/tests/test_runtime_factory.py docker-compose.override.yml .env.example scripts/dev.ps1 tools/runtime/compose_smoke.py tests/test_dev_entrypoint.py tests/test_litellm_compose.py README.md services/api/README.md docs/architecture/agent-runtime.md docs/quality/local-development.md
git commit -m "chore: expose acp runtime deployment contract"
```

## Task 11: Deprecate `/timeline` Authoring UI Consumers

**Files:**
- Modify: `apps/web/src/api.ts`
- Modify: `apps/web/src/types.ts`
- Delete or move: `apps/web/src/shell/conversation/acpTimeline.ts`
- Delete or move: `apps/web/src/shell/conversation/docagentRuntime.ts`
- Modify tests referencing `TimelineEvent` in center-pane code.

- [ ] **Step 1: Add guard test for no authoring UI timeline fetches**

Create `apps/web/src/shell/acp/__tests__/noTimelineAuthoringContract.test.ts`:

```ts
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const shellRoot = join(process.cwd(), "src", "shell");

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry);
    return statSync(path).isDirectory() ? files(path) : [path];
  });
}

it("does not use TimelineEvent as the center-pane authoring contract", () => {
  const offenders = files(shellRoot).filter((path) => {
    const text = readFileSync(path, "utf8");
    return text.includes("TimelineEvent") || text.includes("getTimeline(") || text.includes("/timeline");
  });
  expect(offenders).toEqual([]);
});
```

- [ ] **Step 2: Run guard and verify it fails**

Run:

```powershell
cd apps/web
npm run test:unit -- --run src/shell/acp/__tests__/noTimelineAuthoringContract.test.ts
```

Expected: FAIL while center-pane code still imports `TimelineEvent`, `acpTimeline`, or `docagentRuntime`.

- [ ] **Step 3: Remove center-pane timeline projection files**

Delete `apps/web/src/shell/conversation/acpTimeline.ts` after no imports remain. Delete `docagentRuntime.ts` after moving any generic merge helpers into `acpEvents.ts`.

- [ ] **Step 4: Keep API compatibility explicitly outside shell**

If `api.getTimeline` is still useful for reports or compatibility, keep it in `apps/web/src/api.ts` but do not import it under `apps/web/src/shell`. If no code uses it, remove `getTimeline` and the `TimelineEvent` import from `api.ts`.

- [ ] **Step 5: Run guard and typecheck**

Run:

```powershell
cd apps/web
npm run test:unit -- --run src/shell/acp/__tests__/noTimelineAuthoringContract.test.ts
npm run test
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/web/src apps/web/tests
git commit -m "refactor(web): retire timeline authoring contract"
```

## Task 12: Full Verification And Documentation Sync

**Files:**
- Modify docs if any behavior changed beyond previous tasks.
- No production code changes unless verification exposes a concrete defect.

- [ ] **Step 1: Run frontend unit tests**

Run:

```powershell
cd apps/web
npm run test:unit -- --run
```

Expected: PASS.

- [ ] **Step 2: Run frontend typecheck/build**

Run:

```powershell
cd apps/web
npm run build
```

Expected: PASS. A Vite chunk-size warning is acceptable if no new error appears.

- [ ] **Step 3: Run backend and runtime tests**

Run:

```powershell
.venv\Scripts\python.exe -m pytest packages/contracts/tests packages/timeline/tests services/api/tests agent/runtime-adapters/mock/tests agent/runtime-adapters/openhands/tests tests/test_litellm_compose.py tests/test_dev_entrypoint.py -q --basetemp=.local/pytest-tmp-acp-thin-final
```

Expected: PASS.

- [ ] **Step 4: Run Docker Compose config check**

Run:

```powershell
docker compose config
```

Expected: exit 0. Inspect output for `DOCAGENT_RUNTIME`, `DOCAGENT_ACP_RUNTIME_URL`, `litellm`, and `openhands`.

- [ ] **Step 5: Run source guard searches**

Run:

```powershell
rg -n "@assistant-ui|AssistantRuntimeProvider|useDocAgentAssistantRuntime|projectAcpEventsToTimelineEvents|mergeProjectedAcpEvent" apps/web/src apps/web/package.json
rg -n "OPENHANDS_CONTAINER_BASE_URL|DOCAGENT_RUNTIME=mock$|DOCAGENT_RUNTIME=openhands$" .env.example docker-compose.override.yml scripts/dev.ps1 docs README.md services/api/README.md
```

Expected: no matches except historical docs under `docs/exec-plans/completed` or `docs/superpowers/completed` if the grep command includes them. If historical docs produce matches, rerun with current-truth paths only:

```powershell
rg -n "@assistant-ui|AssistantRuntimeProvider|useDocAgentAssistantRuntime|projectAcpEventsToTimelineEvents|mergeProjectedAcpEvent" apps/web/src apps/web/package.json
rg -n "OPENHANDS_CONTAINER_BASE_URL|DOCAGENT_RUNTIME=mock$|DOCAGENT_RUNTIME=openhands$" .env.example docker-compose.override.yml scripts/dev.ps1 README.md services/api/README.md docs/architecture docs/product docs/quality
```

Expected: no matches.

- [ ] **Step 6: Update plan status and commit final docs**

If verification required doc updates, commit them:

```powershell
git add docs README.md services/api/README.md
git commit -m "docs: sync acp thin client migration"
```

If no files changed, do not create an empty commit.

---

## Verification Commands

Use these before claiming the implementation is complete:

```powershell
cd apps/web
npm run test:unit -- --run
npm run build
```

```powershell
.venv\Scripts\python.exe -m pytest packages/contracts/tests packages/timeline/tests services/api/tests agent/runtime-adapters/mock/tests agent/runtime-adapters/openhands/tests tests/test_litellm_compose.py tests/test_dev_entrypoint.py -q --basetemp=.local/pytest-tmp-acp-thin-final
```

```powershell
docker compose config
```

```powershell
rg -n "@assistant-ui|AssistantRuntimeProvider|useDocAgentAssistantRuntime|projectAcpEventsToTimelineEvents|mergeProjectedAcpEvent" apps/web/src apps/web/package.json
rg -n "OPENHANDS_CONTAINER_BASE_URL|DOCAGENT_RUNTIME=mock$|DOCAGENT_RUNTIME=openhands$" .env.example docker-compose.override.yml scripts/dev.ps1 README.md services/api/README.md docs/architecture docs/product docs/quality
```

## Rollback And Recovery

- If frontend ACP surface integration fails, revert Tasks 3-6 and keep Task 1-2 helper work only if it is unused and passing.
- If assistant-ui removal breaks too much at once, keep the dependency for one task but do not reintroduce it as the center-pane data contract.
- If OpenHands ACP shim behavior differs from tests, preserve raw payloads and render unknown ACP rows rather than adding new semantic projection rules.
- If deployment rename breaks local startup, keep backward-compatible aliases for one release: `mock -> mock-acp`, `openhands -> openhands-acp`, and `OPENHANDS_BASE_URL -> DOCAGENT_ACP_RUNTIME_URL`.
- If `/timeline` consumers remain after Task 11, list them in the plan and classify each as compatibility/reporting or authoring UI before removing more code.

## Open Questions

- Whether to keep a report-only `/timeline` endpoint permanently is outside this implementation. This plan only removes it from the authoring center-pane contract.
- The exact OpenHands native ACP transport may still evolve. The implementation should keep a thin client boundary and tests around event envelope behavior.
