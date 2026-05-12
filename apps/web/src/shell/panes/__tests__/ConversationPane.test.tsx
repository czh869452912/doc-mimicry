import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../../api";
import type { TimelineEvent } from "../../../types";
import { ConversationPane } from "../ConversationPane";

vi.mock("../../../api", () => ({
  api: {
    cancelSession: vi.fn(),
    sendMessage: vi.fn(),
  },
}));

const task = {
  id: "task-1",
  doc_type_id: "prd",
  brief: "Write a PRD",
  title: "PRD task",
  workspace_root: "workspace/task-1",
  created_at: "2026-05-06T08:00:00Z",
  updated_at: "2026-05-06T08:00:00Z",
};

const session = {
  id: "session-1",
  task_id: "task-1",
  status: "draft_ready",
  created_at: "2026-05-06T08:00:00Z",
  updated_at: "2026-05-06T08:00:00Z",
};

const events: TimelineEvent[] = [
  {
    id: "evt-user",
    actor: "user",
    kind: "user_message",
    raw_event_id: null,
    session_id: "session-1",
    summary: "Write a launch PRD",
    paths: [],
    status: "succeeded",
    task_id: "task-1",
  },
];

function renderPane(overrides: Partial<React.ComponentProps<typeof ConversationPane>> = {}) {
  return render(
    <ConversationPane
      activeSession={session}
      activeTask={task}
      ensureSession={vi.fn().mockResolvedValue(session)}
      events={events}
      error={null}
      loading={false}
      refreshTimeline={vi.fn()}
      refreshWorkspace={vi.fn()}
      onOpenPath={vi.fn()}
      {...overrides}
    />,
  );
}

describe("ConversationPane", () => {
  beforeEach(() => {
    class ResizeObserverStub {
      disconnect() {}
      observe() {}
      unobserve() {}
    }

    vi.stubGlobal("ResizeObserver", ResizeObserverStub);
    vi.clearAllMocks();
  });

  it("renders the center pane through assistant-ui thread and composer primitives", () => {
    const { container } = renderPane();

    expect(container.querySelector(".aui-thread")).toBeTruthy();
    expect(container.querySelector(".aui-composer")).toBeTruthy();
    expect(screen.getByRole("button", { name: /copy text/i })).toBeTruthy();
    expect(container.querySelector(".conversation-stream")).toBeFalsy();
    expect(screen.getByText("Write a launch PRD")).toBeTruthy();
  });

  it("renders running status inside the assistant-ui thread", () => {
    render(
      <ConversationPane
        activeSession={{ ...session, status: "running_chat" }}
        activeTask={task}
        ensureSession={vi.fn().mockResolvedValue(session)}
        events={events}
        error={null}
        loading={true}
        refreshTimeline={vi.fn()}
        refreshWorkspace={vi.fn()}
        onOpenPath={vi.fn()}
      />,
    );

    expect(screen.getByText("Agent is working...")).toBeTruthy();
    expect(screen.queryByText("Refreshing timeline...")).toBeFalsy();
  });

  it("submits plain text through the existing DocAgent send message API", async () => {
    vi.mocked(api.sendMessage).mockResolvedValue({ session_id: "session-1", accepted: true, status: "running_chat" });
    renderPane();

    await userEvent.type(screen.getByLabelText("Message"), "Revise this section");
    await userEvent.keyboard("{Enter}");

    expect(api.sendMessage).toHaveBeenCalledWith("session-1", "Revise this section", []);
  });

  it("allows chat from an outline-approval session", async () => {
    vi.mocked(api.sendMessage).mockResolvedValue({ session_id: "session-1", accepted: true, status: "running_chat" });
    renderPane({ activeSession: { ...session, status: "await_outline_approval" } });

    await userEvent.type(screen.getByLabelText("Message"), "Adjust the outline");
    await userEvent.keyboard("{Enter}");

    expect(api.sendMessage).toHaveBeenCalledWith("session-1", "Adjust the outline", []);
  });

  it("does not submit or cancel when Enter is pressed while running", async () => {
    renderPane({ activeSession: { ...session, status: "running_chat" } });

    await userEvent.type(screen.getByLabelText("Message"), "Do not cancel");
    await userEvent.keyboard("{Enter}");

    expect(api.cancelSession).not.toHaveBeenCalled();
    expect(api.sendMessage).not.toHaveBeenCalled();
  });
});
