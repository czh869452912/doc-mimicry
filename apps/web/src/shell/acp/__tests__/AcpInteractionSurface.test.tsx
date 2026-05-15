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
