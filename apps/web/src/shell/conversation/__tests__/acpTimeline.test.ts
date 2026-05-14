import { describe, expect, it } from "vitest";
import type { AcpEvent } from "../../../types";
import {
  mergeProjectedAcpEvent,
  projectAcpEventsToTimelineEvents,
} from "../acpTimeline";

function acp(overrides: Partial<AcpEvent> & Pick<AcpEvent, "id" | "sequence" | "event_type">): AcpEvent {
  return {
    session_id: "session-1",
    payload: {},
    projection: {},
    created_at: "2026-05-14T00:00:00Z",
    ...overrides,
  };
}

describe("ACP timeline projection", () => {
  it("merges assistant message chunks into one streaming timeline message", () => {
    const events = projectAcpEventsToTimelineEvents(
      [
        acp({
          id: "acp-1",
          sequence: 1,
          event_type: "message_delta",
          payload: { role: "assistant", content: "Hel", message_id: "msg-1" },
        }),
        acp({
          id: "acp-2",
          sequence: 2,
          event_type: "message_delta",
          payload: { role: "assistant", content: "lo", message_id: "msg-1" },
        }),
        acp({
          id: "acp-3",
          sequence: 3,
          event_type: "message_completed",
          payload: { role: "assistant", message_id: "msg-1" },
        }),
      ],
      "task-1",
    );

    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({
      id: "acp-message-msg-1",
      actor: "agent",
      kind: "agent_message",
      status: "succeeded",
      summary: "Hello",
      task_id: "task-1",
    });
    expect(events[0].raw_acp_event?.id).toBe("acp-3");
  });

  it("updates tool call status and paths by stable tool call id", () => {
    const events = projectAcpEventsToTimelineEvents(
      [
        acp({
          id: "acp-4",
          sequence: 4,
          event_type: "tool_call",
          payload: { id: "tool-1", name: "write_file", status: "running" },
        }),
        acp({
          id: "acp-5",
          sequence: 5,
          event_type: "tool_result",
          payload: { id: "tool-1", name: "write_file", status: "succeeded", paths: ["draft/draft.md"] },
        }),
      ],
      "task-1",
    );

    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({
      id: "acp-tool-tool-1",
      kind: "agent_tool_call",
      status: "succeeded",
      paths: ["draft/draft.md"],
      summary: "write_file succeeded",
    });
  });

  it("routes DocAgent projection metadata into existing semantic card kinds", () => {
    const [event] = projectAcpEventsToTimelineEvents(
      [
        acp({
          id: "acp-6",
          sequence: 6,
          event_type: "docagent/projection",
          payload: { method: "docagent/projection" },
          projection: {
            timeline_id: "outline-1",
            timeline_kind: "propose_outline",
            actor: "agent",
            summary: "Review outline",
            paths: ["draft/outline.md"],
            status: "pending",
          },
        }),
      ],
      "task-1",
    );

    expect(event).toMatchObject({
      id: "outline-1",
      kind: "propose_outline",
      summary: "Review outline",
      paths: ["draft/outline.md"],
      status: "pending",
    });
  });

  it("incrementally appends a message chunk to existing projected events", () => {
    const [first] = projectAcpEventsToTimelineEvents(
      [
        acp({
          id: "acp-7",
          sequence: 7,
          event_type: "message_delta",
          payload: { role: "assistant", content: "Draft", message_id: "msg-2" },
        }),
      ],
      "task-1",
    );

    const next = mergeProjectedAcpEvent(
      [first],
      acp({
        id: "acp-8",
        sequence: 8,
        event_type: "message_delta",
        payload: { role: "assistant", content: " updated", message_id: "msg-2" },
      }),
      "task-1",
    );

    expect(next).toHaveLength(1);
    expect(next[0].summary).toBe("Draft updated");
    expect(next[0].status).toBe("running");
  });
});
