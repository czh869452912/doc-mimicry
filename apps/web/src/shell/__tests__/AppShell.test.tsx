import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../api";
import { AppShell } from "../AppShell";

vi.mock("../../api", () => ({
  api: {
    approveOutline: vi.fn(),
    createSession: vi.fn(),
    createTask: vi.fn(),
    exportMarkdown: vi.fn(),
    getDraft: vi.fn(),
    getTimeline: vi.fn(),
    getWorkspace: vi.fn(),
    getWorkspaceFile: vi.fn(),
    listDocTypes: vi.fn(),
    listTaskSessions: vi.fn(),
    listTasks: vi.fn(),
    runChecklist: vi.fn(),
    sendMessage: vi.fn(),
    startLoop: vi.fn(),
    updateDraft: vi.fn(),
  },
}));

vi.mock("react-resizable-panels", () => ({
  Group: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Panel: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Separator: () => <div />,
}));

describe("AppShell", () => {
  beforeEach(() => {
    class ResizeObserverStub {
      disconnect() {}
      observe() {}
      unobserve() {}
    }

    vi.stubGlobal("ResizeObserver", ResizeObserverStub);
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
    window.localStorage.clear();
    vi.clearAllMocks();
    vi.mocked(api.listDocTypes).mockResolvedValue([
      { id: "prd", title: "PRD", has_skill: true, resource_groups: {} },
    ]);
    vi.mocked(api.listTasks).mockResolvedValue([
      {
        id: "task-1",
        doc_type_id: "prd",
        brief: "Write a PRD",
        workspace_root: "workspace/task-1",
        created_at: "2026-05-06T08:00:00Z",
        updated_at: "2026-05-06T09:00:00Z",
      },
    ]);
    vi.mocked(api.listTaskSessions).mockResolvedValue([
      {
        id: "session-1",
        task_id: "task-1",
        status: "draft_ready",
        created_at: "2026-05-06T08:00:00Z",
        updated_at: "2026-05-06T09:00:00Z",
      },
    ]);
    vi.mocked(api.getWorkspace).mockResolvedValue({ task_id: "task-1", root: "workspace/task-1", files: [] });
    vi.mocked(api.getTimeline).mockResolvedValue([]);
    vi.mocked(api.getDraft).mockResolvedValue({ markdown: "# Restored draft" });
    vi.mocked(api.updateDraft).mockResolvedValue({ markdown: "# Restored draft" });
  });

  it("loads the active task draft after restored workspace state is available", async () => {
    render(<AppShell />);

    await waitFor(() => expect(api.getDraft).toHaveBeenCalledWith("task-1"));
    expect(await screen.findByRole("heading", { name: "Restored draft" })).toBeTruthy();
  });

  it("runs slash commands selected from the command palette", async () => {
    render(<AppShell />);

    await screen.findByText("Write a PRD");
    await userEvent.click(screen.getByText("Ctrl K"));
    await userEvent.click(screen.getByText("/help"));

    expect(await screen.findByText("Slash commands")).toBeTruthy();
  });
});
