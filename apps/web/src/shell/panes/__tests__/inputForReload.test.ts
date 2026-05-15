import { describe, expect, it } from "vitest";
import type { AcpEvent } from "../../../types";
import { findReloadInput } from "../../acp/acpEvents";

function userEvent(id: string, prompt: string): AcpEvent {
  return {
    id,
    session_id: "s1",
    sequence: Number(id.replace(/\D/g, "")) || 1,
    event_type: "docagent/prompt",
    payload: { prompt },
    projection: {},
    created_at: "2026-05-15T00:00:00Z",
  };
}

function agentEvent(id: string, summary: string): AcpEvent {
  return {
    id,
    session_id: "s1",
    sequence: Number(id.replace(/\D/g, "")) || 1,
    event_type: "message_delta",
    payload: { role: "assistant", content: summary },
    projection: {},
    created_at: "2026-05-15T00:00:00Z",
  };
}

describe("findReloadInput", () => {
  it("returns null for empty timeline", () => {
    expect(findReloadInput([], null)).toBeNull();
  });

  it("returns last user message when parentMessageId is null", () => {
    const events = [
      userEvent("u1", "First message"),
      agentEvent("a1", "Agent reply"),
      userEvent("u2", "Last message"),
    ];
    expect(findReloadInput(events, null)).toBe("Last message");
  });

  it("returns the previous user message when the selected event is a user event", () => {
    const events = [
      userEvent("u1", "First"),
      userEvent("u2", "Target"),
      agentEvent("a1", "Reply"),
    ];
    expect(findReloadInput(events, "u2")).toBe("First");
  });

  it("skips agent messages and finds previous user message", () => {
    const events = [
      userEvent("u1", "First"),
      agentEvent("a1", "Agent"),
      agentEvent("a2", "Another agent"),
    ];
    expect(findReloadInput(events, "a2")).toBe("First");
  });

  it("returns null when no user message found", () => {
    const events = [agentEvent("a1", "Only agent")];
    expect(findReloadInput(events, null)).toBeNull();
  });

  it("falls back to the latest user message when parentMessageId is not found", () => {
    const events = [userEvent("u1", "Only")];
    expect(findReloadInput(events, "nonexistent")).toBe("Only");
  });

  it("skips empty user messages", () => {
    const events = [
      userEvent("u1", "   "),
      userEvent("u2", "Valid"),
    ];
    expect(findReloadInput(events, null)).toBe("Valid");
  });
});
