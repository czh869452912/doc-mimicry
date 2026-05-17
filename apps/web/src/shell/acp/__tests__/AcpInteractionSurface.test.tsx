import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../../api";
import type { AcpEvent } from "../../../types";
import { AcpInteractionSurface } from "../AcpInteractionSurface";

vi.mock("../../../api", () => ({
  api: {
    importFileInput: vi.fn(),
  },
}));

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

  it("renders ACP user, assistant, tool, file, status, and unknown event titles", () => {
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
    expect(screen.queryByText(/"hello"/i)).toBeNull();
  });

  it("hides OpenHands housekeeping events from the fallback center pane", () => {
    render(
      <AcpInteractionSurface
        {...baseProps}
        events={[
          acp({
            id: "session-created",
            sequence: 1,
            event_type: "openhands/session_created",
            payload: { workspace_root: "/workspace/state/workspaces/task-1" },
          }),
          acp({
            id: "state-update",
            sequence: 2,
            event_type: "openhands/ConversationStateUpdateEvent",
            payload: { key: "execution_status", value: "running" },
          }),
          acp({ id: "message", sequence: 3, event_type: "message_delta", payload: { role: "assistant", content: "Visible" } }),
        ]}
      />,
    );

    expect(screen.getByText("Visible")).toBeTruthy();
    expect(screen.queryByText(/session_created/i)).toBeNull();
    expect(screen.queryByText(/ConversationStateUpdateEvent/i)).toBeNull();
    expect(screen.queryByText(/execution_status/i)).toBeNull();
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

  it("keeps compatibility projection mirrors out of the center pane when a native ACP event carries the same projection", () => {
    render(
      <AcpInteractionSurface
        {...baseProps}
        events={[
          acp({
            id: "native-checklist",
            sequence: 1,
            event_type: "file/write",
            payload: { path: "reviews/checklist_result.md" },
            projection: {
              timeline_id: "timeline-checklist",
              timeline_kind: "run_checklist",
              summary: "Run checklist",
              paths: ["reviews/checklist_result.md"],
              status: "succeeded",
            },
          }),
          acp({
            id: "projection-checklist",
            sequence: 2,
            event_type: "docagent/projection",
            payload: { method: "docagent/projection", timeline_event_id: "timeline-checklist" },
            projection: {
              timeline_id: "timeline-checklist",
              timeline_kind: "run_checklist",
              summary: "Run checklist",
              paths: ["reviews/checklist_result.md"],
              status: "succeeded",
            },
          }),
        ]}
      />,
    );

    expect(screen.getAllByText("Checklist · succeeded")).toHaveLength(1);
    expect(screen.queryByText("docagent/projection")).toBeNull();
  });

  it("keeps projection-backed product cards visible when no native ACP event exists yet", () => {
    render(
      <AcpInteractionSurface
        {...baseProps}
        events={[
          acp({
            id: "projection-checklist",
            sequence: 1,
            event_type: "docagent/projection",
            payload: { method: "docagent/projection", timeline_event_id: "timeline-checklist" },
            projection: {
              timeline_id: "timeline-checklist",
              timeline_kind: "run_checklist",
              summary: "Run checklist",
              paths: ["reviews/checklist_result.md"],
              status: "succeeded",
            },
          }),
        ]}
      />,
    );

    expect(screen.getByText("Checklist · succeeded")).toBeTruthy();
  });

  it("renders projection-backed manual checkpoint cards", () => {
    render(
      <AcpInteractionSurface
        {...baseProps}
        events={[
          acp({
            id: "projection-checkpoint",
            sequence: 1,
            event_type: "docagent/projection",
            payload: { method: "docagent/projection", timeline_event_id: "timeline-checkpoint" },
            projection: {
              timeline_id: "timeline-checkpoint",
              timeline_kind: "create_checkpoint",
              summary: "Manual checkpoint",
              paths: ["versions/v001.md"],
              status: "succeeded",
            },
          }),
        ]}
      />,
    );

    expect(screen.getByText("Checkpoint · versions/v001.md")).toBeTruthy();
    expect(screen.getByText("Manual checkpoint")).toBeTruthy();
  });

  it("renders manual checkpoint cards without leaking undefined when no path is available", () => {
    render(
      <AcpInteractionSurface
        {...baseProps}
        events={[
          acp({
            id: "projection-checkpoint",
            sequence: 1,
            event_type: "docagent/projection",
            payload: { method: "docagent/projection", timeline_event_id: "timeline-checkpoint" },
            projection: {
              timeline_id: "timeline-checkpoint",
              timeline_kind: "create_checkpoint",
              summary: "Manual checkpoint",
              paths: [],
              status: "succeeded",
            },
          }),
        ]}
      />,
    );

    expect(screen.getByText("Checkpoint · succeeded")).toBeTruthy();
    expect(screen.queryByText(/undefined/i)).toBeNull();
    expect(screen.queryByRole("button", { name: /open/i })).toBeNull();
  });

  it("does not render non-card DocAgent projection mirrors in the center pane", () => {
    render(
      <AcpInteractionSurface
        {...baseProps}
        events={[
          acp({
            id: "projection-status",
            sequence: 1,
            event_type: "docagent/projection",
            payload: { method: "docagent/projection", timeline_event_id: "timeline-status" },
            projection: {
              timeline_id: "timeline-status",
              timeline_kind: "session_status",
              summary: "Session status changed to draft_ready",
              status: "succeeded",
            },
          }),
        ]}
      />,
    );

    expect(screen.queryByText("Session status changed to draft_ready")).toBeNull();
    expect(screen.queryByText("docagent/projection")).toBeNull();
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

  it("does not render decision actions for completed permission events", () => {
    const onAnswerPermission = vi.fn().mockResolvedValue(undefined);
    render(
      <AcpInteractionSurface
        {...baseProps}
        onAnswerPermission={onAnswerPermission}
        events={[
          acp({
            id: "resolved",
            sequence: 1,
            event_type: "permission/resolved",
            payload: { request_id: "permission-1", decision: "allow" },
          }),
          acp({
            id: "response",
            sequence: 2,
            event_type: "permission/response",
            payload: { request_id: "permission-1", decision: "allow" },
          }),
        ]}
      />,
    );

    expect(screen.queryByRole("button", { name: /allow permission request/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /deny permission request/i })).toBeNull();
  });

  it("forwards imported attachments through the stable surface callback", async () => {
    const user = userEvent.setup();
    const onAttachContext = vi.fn().mockResolvedValue(undefined);
    vi.mocked(api.importFileInput).mockResolvedValue({
      id: "input-1",
      status: "converted",
      source_path: "inputs/original/context.txt",
      markdown_path: "inputs/markdown/context.md",
      conversion_report_path: "inputs/reports/context.json",
      original_filename: "context.txt",
      created_at: "2026-05-15T00:00:00Z",
    });
    render(
      <AcpInteractionSurface
        {...baseProps}
        events={[]}
        onAttachContext={onAttachContext}
      />,
    );

    await user.upload(
      document.querySelector('input[type="file"]') as HTMLInputElement,
      new File(["Attachment context"], "context.txt", { type: "text/plain" }),
    );
    await user.type(screen.getByLabelText("Message"), "Use context");
    await user.click(screen.getByRole("button", { name: /send message/i }));

    await waitFor(() => expect(onAttachContext).toHaveBeenCalledWith([
      {
        name: "context.txt",
        markdown_path: "inputs/markdown/context.md",
        source_path: "inputs/original/context.txt",
        conversion_report_path: "inputs/reports/context.json",
      },
    ]));
  });
});
