import { describe, expect, it } from "vitest";
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

  it("recognizes interim projection status metadata for session invalidation", () => {
    const hints = deriveAcpInvalidationHints([
      acp({
        id: "projection-status",
        sequence: 1,
        event_type: "docagent/projection",
        projection: { timeline_kind: "session_status" },
      }),
    ]);

    expect(hints.sessions).toBe(true);
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
