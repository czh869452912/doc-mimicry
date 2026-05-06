import { describe, expect, it } from "vitest";
import type { TimelineEvent } from "../../types";
import { KNOWN_TIMELINE_KINDS, timelinePresentation } from "../conversation/timelinePresentation";

function event(kind: string, paths: string[] = []): TimelineEvent {
  return {
    actor: kind === "user_message" ? "user" : "agent",
    id: `event-${kind}`,
    kind,
    paths,
    status: "succeeded",
    summary: `Summary for ${kind}`,
  };
}

describe("timelinePresentation", () => {
  it("covers every current SemanticEventKind string", () => {
    const presentations = KNOWN_TIMELINE_KINDS.map((kind) =>
      timelinePresentation(event(kind, kind === "propose_outline" ? ["draft/outline.md"] : [])),
    );

    expect(presentations).toHaveLength(21);
    expect(presentations.every((presentation) => presentation.kind)).toBe(true);
  });

  it("maps messages to message presentations", () => {
    expect(timelinePresentation(event("user_message")).kind).toBe("message");
    expect(timelinePresentation(event("agent_message")).kind).toBe("message");
  });

  it("maps outline, checklist, approval, and artifact events to cards", () => {
    expect(timelinePresentation(event("propose_outline", ["draft/outline.md"]))).toMatchObject({
      kind: "card",
      cardType: "outline",
    });
    expect(timelinePresentation(event("run_checklist"))).toMatchObject({ kind: "card", cardType: "checklist" });
    expect(timelinePresentation(event("approval_requested"))).toMatchObject({ kind: "card", cardType: "approval" });
    expect(timelinePresentation(event("export_markdown"))).toMatchObject({ kind: "card", cardType: "artifact" });
  });

  it("keeps unknown events visible as fallback pills", () => {
    expect(timelinePresentation(event("new_runtime_event"))).toMatchObject({
      kind: "pill",
      category: "thinking",
      summary: "Summary for new_runtime_event",
    });
  });
});
