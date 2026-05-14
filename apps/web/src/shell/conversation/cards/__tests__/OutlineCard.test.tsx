import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../../../api";
import type { TimelineEvent } from "../../../../types";
import { OutlineCard } from "../OutlineCard";

vi.mock("../../../../api", () => ({
  api: {
    approveOutline: vi.fn(),
    getWorkspaceFile: vi.fn(),
  },
}));

const event: TimelineEvent = {
  actor: "agent",
  id: "evt-outline",
  kind: "propose_outline",
  paths: ["draft/outline.md"],
  raw_event_id: null,
  session_id: "session-1",
  status: "succeeded",
  summary: "Initial summary",
  task_id: "task-1",
};

describe("OutlineCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does not overwrite local outline edits when the file fetch resolves late", async () => {
    const user = userEvent.setup();
    let resolveFile!: (value: { content: string; path: string }) => void;
    vi.mocked(api.getWorkspaceFile).mockReturnValue(
      new Promise((resolve) => {
        resolveFile = resolve;
      }) as ReturnType<typeof api.getWorkspaceFile>,
    );

    render(
      <OutlineCard
        event={event}
        sessionId="session-1"
        taskId="task-1"
        onApproved={vi.fn()}
        onOpenPath={vi.fn()}
      />,
    );

    const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
    await user.clear(textarea);
    await user.type(textarea, "User edited outline");
    resolveFile({ path: "draft/outline.md", content: "Fetched outline" });

    await waitFor(() => {
      expect(textarea.value).toBe("User edited outline");
    });
  });

  it("approves the edited outline", async () => {
    const user = userEvent.setup();
    vi.mocked(api.getWorkspaceFile).mockResolvedValue({ path: "draft/outline.md", content: "Fetched outline" });
    const onApproved = vi.fn().mockResolvedValue(undefined);

    render(
      <OutlineCard
        event={event}
        sessionId="session-1"
        taskId="task-1"
        onApproved={onApproved}
        onOpenPath={vi.fn()}
      />,
    );

    const textarea = (await screen.findByRole("textbox")) as HTMLTextAreaElement;
    await user.clear(textarea);
    await user.type(textarea, "Approved local outline");
    await user.click(screen.getByRole("button", { name: /approve/i }));

    expect(api.approveOutline).toHaveBeenCalledWith("session-1", "Approved local outline");
    expect(onApproved).toHaveBeenCalledTimes(1);
  });

  it("does not overwrite dirty edits when the same outline event receives a summary update", async () => {
    const user = userEvent.setup();
    vi.mocked(api.getWorkspaceFile).mockResolvedValue({ path: "draft/outline.md", content: "Fetched outline" });
    const props = {
      event,
      sessionId: "session-1",
      taskId: "task-1",
      onApproved: vi.fn().mockResolvedValue(undefined),
      onOpenPath: vi.fn(),
    };
    const { rerender } = render(<OutlineCard {...props} />);

    const textarea = (await screen.findByRole("textbox")) as HTMLTextAreaElement;
    await user.clear(textarea);
    await user.type(textarea, "User edited outline");

    rerender(
      <OutlineCard
        {...props}
        event={{
          ...event,
          summary: "Server pushed a fresher summary for the same event",
        }}
      />,
    );

    await waitFor(() => {
      expect(api.getWorkspaceFile).toHaveBeenCalledTimes(1);
    });
    expect(textarea.value).toBe("User edited outline");
  });
});
