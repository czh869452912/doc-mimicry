import { describe, expect, it } from "vitest";
import type { TimelineEvent } from "../../../types";
import { mapTimelineEventsToAssistantMessages } from "../docAgentAssistantMessages";

function event(overrides: Partial<TimelineEvent> & Pick<TimelineEvent, "id" | "kind" | "summary">): TimelineEvent {
  return {
    actor: "agent",
    paths: [],
    status: "succeeded",
    ...overrides,
  };
}

describe("mapTimelineEventsToAssistantMessages", () => {
  it("maps user and agent timeline messages to assistant-ui text messages", () => {
    const messages = mapTimelineEventsToAssistantMessages([
      event({ id: "evt-user", actor: "user", kind: "user_message", summary: "Write a PRD" }),
      event({ id: "evt-agent", kind: "agent_message", summary: "I will draft it." }),
    ]);

    expect(messages).toMatchObject([
      {
        id: "evt-user",
        role: "user",
        content: [{ type: "text", text: "Write a PRD" }],
        attachments: [],
        metadata: { custom: { timelineEventId: "evt-user", timelineKind: "user_message" } },
      },
      {
        id: "evt-agent",
        role: "assistant",
        content: [{ type: "text", text: "I will draft it." }],
        status: { type: "complete", reason: "stop" },
        metadata: { custom: { timelineEventId: "evt-agent", timelineKind: "agent_message" } },
      },
    ]);
  });

  it("maps semantic timeline cards to assistant-ui data parts", () => {
    const messages = mapTimelineEventsToAssistantMessages([
      event({
        id: "evt-outline",
        kind: "propose_outline",
        summary: "Review the outline",
        paths: ["draft/outline.md"],
      }),
      event({ id: "evt-checklist", kind: "run_checklist", summary: "Checklist complete" }),
      event({
        id: "evt-export",
        kind: "export_markdown",
        summary: "Markdown exported",
        paths: ["artifacts/export.md"],
      }),
      event({ id: "evt-approval", kind: "approval_requested", summary: "Approval needed" }),
    ]);

    expect(messages.map((message) => message.content[0])).toMatchObject([
      { type: "data", name: "docagent.outline-card", data: { kind: "outline-card" } },
      { type: "data", name: "docagent.checklist-card", data: { kind: "checklist-card" } },
      { type: "data", name: "docagent.artifact-card", data: { kind: "artifact-card" } },
      { type: "data", name: "docagent.approval-card", data: { kind: "approval-card" } },
    ]);
  });

  it("maps semantic work events to assistant-ui tool-call data parts", () => {
    const messages = mapTimelineEventsToAssistantMessages([
      event({
        id: "evt-context",
        kind: "build_context",
        summary: "Built context files",
        paths: ["context/user_intent.md", "context/doc_map.md"],
      }),
    ]);

    expect(messages[0]).toMatchObject({
      id: "evt-context",
      role: "assistant",
      content: [
        {
          type: "data",
          name: "docagent.tool-call",
          data: {
            kind: "tool-call",
            toolName: "build_context",
            title: "Build context",
            category: "write",
            status: "succeeded",
            summary: "Built context files",
            paths: ["context/user_intent.md", "context/doc_map.md"],
            pathSummary: "context/user_intent.md, context/doc_map.md",
          },
        },
      ],
      metadata: { custom: { timelineEventId: "evt-context", timelineKind: "build_context" } },
    });
  });

  it("normalizes tool-call display status from timeline status", () => {
    const messages = mapTimelineEventsToAssistantMessages([
      event({ id: "evt-failed", kind: "update_draft", summary: "Draft failed", status: "failed" }),
      event({ id: "evt-running", kind: "generate_outline", summary: "Generating", status: "running" }),
    ]);

    expect(messages.map((message) => message.content[0])).toMatchObject([
      { type: "data", name: "docagent.tool-call", data: { status: "failed" } },
      { type: "data", name: "docagent.tool-call", data: { status: "running" } },
    ]);
  });
});
