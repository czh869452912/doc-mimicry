import { describe, expect, it } from "vitest";
import type { TimelineEvent } from "../../../types";
import { inputForReload } from "../ConversationPane";

function userEvent(id: string, summary: string): TimelineEvent {
  return {
    id,
    actor: "user",
    kind: "user_message",
    raw_event_id: null,
    session_id: "s1",
    summary,
    paths: [],
    status: "succeeded",
    task_id: "t1",
  };
}

function agentEvent(id: string, summary: string): TimelineEvent {
  return {
    id,
    actor: "agent",
    kind: "agent_message",
    raw_event_id: null,
    session_id: "s1",
    summary,
    paths: [],
    status: "succeeded",
    task_id: "t1",
  };
}

describe("inputForReload", () => {
  it("returns null for empty timeline", () => {
    expect(inputForReload([], null)).toBeNull();
  });

  it("returns last user message when parentMessageId is null", () => {
    const events = [
      userEvent("u1", "First message"),
      agentEvent("a1", "Agent reply"),
      userEvent("u2", "Last message"),
    ];
    expect(inputForReload(events, null)).toBe("Last message");
  });

  it("returns parent message when it is a user message", () => {
    const events = [
      userEvent("u1", "First"),
      userEvent("u2", "Target"),
      agentEvent("a1", "Reply"),
    ];
    expect(inputForReload(events, "u2")).toBe("Target");
  });

  it("skips agent messages and finds previous user message", () => {
    const events = [
      userEvent("u1", "First"),
      agentEvent("a1", "Agent"),
      agentEvent("a2", "Another agent"),
    ];
    expect(inputForReload(events, "a2")).toBe("First");
  });

  it("returns null when no user message found", () => {
    const events = [agentEvent("a1", "Only agent")];
    expect(inputForReload(events, null)).toBeNull();
  });

  it("falls back to the latest user message when parentMessageId is not found", () => {
    const events = [userEvent("u1", "Only")];
    expect(inputForReload(events, "nonexistent")).toBe("Only");
  });

  it("skips empty user messages", () => {
    const events = [
      userEvent("u1", "   "),
      userEvent("u2", "Valid"),
    ];
    expect(inputForReload(events, null)).toBe("Valid");
  });
});
