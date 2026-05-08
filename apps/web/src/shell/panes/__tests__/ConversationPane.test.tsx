import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../../api";
import type { TimelineEvent } from "../../../types";
import { ConversationPane } from "../ConversationPane";

vi.mock("../../../api", () => ({
  api: {
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
  status: "idle",
  created_at: "2026-05-06T08:00:00Z",
  updated_at: "2026-05-06T08:00:00Z",
};

const events: TimelineEvent[] = [
  {
      id: "evt-user",
      actor: "user",
      kind: "user_message",
      summary: "Write a launch PRD",
      paths: [],
      status: "succeeded",
  },
];

function renderPane() {
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
    expect(container.querySelector(".conversation-stream")).toBeFalsy();
    expect(screen.getByText("Write a launch PRD")).toBeTruthy();
  });

  it("submits plain text through the existing DocAgent send message API", async () => {
    vi.mocked(api.sendMessage).mockResolvedValue({ accepted: true, status: "running_chat" });
    renderPane();

    await userEvent.type(screen.getByLabelText("Message"), "Revise this section");
    await userEvent.keyboard("{Enter}");

    expect(api.sendMessage).toHaveBeenCalledWith("session-1", "Revise this section");
  });
});
