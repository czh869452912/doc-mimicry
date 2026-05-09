import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { TimelineEvent } from "../../../types";
import type { DocAgentAssistantData } from "../docAgentAssistantMessages";
import { DocAgentMessagePart } from "../DocAgentMessageParts";

vi.mock("../../../api", () => ({
  api: {
    getWorkspaceFile: vi.fn().mockResolvedValue({ content: "# Outline" }),
  },
}));

function event(overrides: Partial<TimelineEvent> & Pick<TimelineEvent, "id" | "kind" | "summary">): TimelineEvent {
  return {
    actor: "agent",
    paths: [],
    raw_event_id: null,
    session_id: "test-session",
    status: "succeeded",
    task_id: "test-task",
    ...overrides,
  };
}

function renderPart(data: DocAgentAssistantData) {
  return render(
    <DocAgentMessagePart
      activeSessionId="session-1"
      data={data}
      taskId="task-1"
      onApproved={vi.fn()}
      onOpenPath={vi.fn()}
    />,
  );
}

describe("DocAgentMessagePart", () => {
  it("renders tool-call data parts", () => {
    const { container } = renderPart({
      kind: "tool-call",
      category: "write",
      toolName: "build_context",
      title: "Build context",
      status: "succeeded",
      summary: "Built context",
      paths: ["context/brief.md"],
      pathSummary: "context/brief.md",
      event: event({ id: "evt-context", kind: "build_context", summary: "Built context" }),
    });

    expect(container.querySelector(".aui-tool-call")).toBeTruthy();
    expect(screen.getByText("Build context")).toBeTruthy();
    expect(screen.getByText("succeeded")).toBeTruthy();
    expect(screen.getByText("Built context")).toBeTruthy();
    expect(screen.getByText("context/brief.md")).toBeTruthy();
  });

  it("renders outline, checklist, artifact, and approval card data parts", () => {
    const { container, rerender } = renderPart({
      kind: "outline-card",
      event: event({
        id: "evt-outline",
        kind: "propose_outline",
        summary: "Review outline",
        paths: ["draft/outline.md"],
      }),
    });
    expect(container.querySelector(".aui-timeline-part--card")).toBeTruthy();
    expect(screen.getByText("Outline · waiting for review")).toBeTruthy();

    rerender(
      <DocAgentMessagePart
        activeSessionId="session-1"
        data={{
          kind: "checklist-card",
          event: event({
            id: "evt-checklist",
            kind: "run_checklist",
            summary: "Checklist passed",
            paths: ["reviews/checklist.md"],
          }),
        }}
        taskId="task-1"
        onApproved={vi.fn()}
        onOpenPath={vi.fn()}
      />,
    );
    expect(screen.getByText("Checklist · succeeded")).toBeTruthy();

    rerender(
      <DocAgentMessagePart
        activeSessionId="session-1"
        data={{
          kind: "artifact-card",
          event: event({
            id: "evt-export",
            kind: "export_markdown",
            summary: "Exported markdown",
            paths: ["artifacts/export.md"],
          }),
        }}
        taskId="task-1"
        onApproved={vi.fn()}
        onOpenPath={vi.fn()}
      />,
    );
    expect(screen.getByText("Artifact · artifacts/export.md")).toBeTruthy();

    rerender(
      <DocAgentMessagePart
        activeSessionId="session-1"
        data={{
          kind: "approval-card",
          event: event({ id: "evt-approval", kind: "approval_requested", summary: "Approve this?" }),
        }}
        taskId="task-1"
        onApproved={vi.fn()}
        onOpenPath={vi.fn()}
      />,
    );
    expect(screen.getByText("Approval requested")).toBeTruthy();
  });
});
