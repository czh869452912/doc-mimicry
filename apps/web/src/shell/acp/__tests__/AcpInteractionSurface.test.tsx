import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
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
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
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

    expect(screen.getByText("Write a PRD")).toBeTruthy();
    expect(screen.getByText("Working")).toBeTruthy();
    expect(screen.getByText(/read_file/i)).toBeTruthy();
    expect(screen.getAllByText(/draft\/draft\.md/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Session status/i)).toBeTruthy();
    expect(screen.getByText(/vendor\/custom/i)).toBeTruthy();
  });

  it("copies event text with local ACP actions", async () => {
    const user = userEvent.setup({ writeToClipboard: false });
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    render(
      <AcpInteractionSurface
        {...baseProps}
        events={[acp({ id: "a", sequence: 1, event_type: "message_delta", payload: { content: "Copy me" } })]}
      />,
    );

    await user.click(screen.getByRole("button", { name: /copy/i }));
    expect(writeText).toHaveBeenCalledWith("Copy me");
  });

  it("delegates copy behavior through the stable surface callback when supplied", async () => {
    const user = userEvent.setup();
    const onCopyContent = vi.fn().mockResolvedValue(undefined);
    render(
      <AcpInteractionSurface
        {...baseProps}
        onCopyContent={onCopyContent}
        events={[acp({ id: "a", sequence: 1, event_type: "message_delta", payload: { content: "Copy through port" } })]}
      />,
    );

    await user.click(screen.getByRole("button", { name: /copy/i }));
    expect(onCopyContent).toHaveBeenCalledWith({ text: "Copy through port", eventId: "a" });
  });

  it("uses injected render slots for product cards", () => {
    const renderSlots = vi.fn(({ event }: { event: AcpEvent }) => <div>Custom slot for {event.id}</div>);
    render(
      <AcpInteractionSurface
        {...baseProps}
        renderSlots={renderSlots}
        events={[
          acp({
            id: "slot-1",
            sequence: 1,
            event_type: "file/write",
            payload: { path: "reviews/checklist_result.md" },
            projection: { timeline_kind: "run_checklist" },
          }),
        ]}
      />,
    );

    expect(screen.getByText("Custom slot for slot-1")).toBeTruthy();
    expect(renderSlots).toHaveBeenCalled();
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

  it("requests reload for the latest user input when no event is selected", async () => {
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

    await user.click(screen.getByRole("button", { name: /reload last user message/i }));
    expect(onReloadInput).toHaveBeenCalledWith(null);
  });

  it("answers permission requests with the request id and decision", async () => {
    const user = userEvent.setup();
    const onAnswerPermission = vi.fn().mockResolvedValue(undefined);
    render(
      <AcpInteractionSurface
        {...baseProps}
        onAnswerPermission={onAnswerPermission}
        events={[
          acp({
            id: "p",
            sequence: 1,
            event_type: "permission/request",
            payload: { request_id: "permission-1", message: "Allow file write?" },
          }),
        ]}
      />,
    );

    await user.click(screen.getByRole("button", { name: /allow permission request/i }));
    await user.click(screen.getByRole("button", { name: /deny permission request/i }));

    expect(onAnswerPermission).toHaveBeenNthCalledWith(1, "permission-1", "allow");
    expect(onAnswerPermission).toHaveBeenNthCalledWith(2, "permission-1", "deny");
  });
});
