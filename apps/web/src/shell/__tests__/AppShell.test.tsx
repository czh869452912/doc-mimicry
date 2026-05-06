import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
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

  afterEach(() => {
    vi.useRealTimers();
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

  it("does not autosave the previous task draft into a newly selected task while that draft loads", async () => {
    let resolveTaskTwoDraft!: (value: { markdown: string }) => void;

    vi.mocked(api.listTasks).mockResolvedValue([
      {
        id: "task-1",
        doc_type_id: "prd",
        brief: "Task One",
        workspace_root: "workspace/task-1",
        created_at: "2026-05-06T08:00:00Z",
        updated_at: "2026-05-06T09:00:00Z",
      },
      {
        id: "task-2",
        doc_type_id: "prd",
        brief: "Task Two",
        workspace_root: "workspace/task-2",
        created_at: "2026-05-06T08:00:00Z",
        updated_at: "2026-05-06T09:30:00Z",
      },
    ]);
    vi.mocked(api.getDraft).mockImplementation((taskId) => {
      if (taskId === "task-1") return Promise.resolve({ markdown: "# Task one draft" });
      return new Promise((resolve) => {
        resolveTaskTwoDraft = resolve;
      });
    });
    window.localStorage.setItem("docagent:lastTaskId", "task-1");

    render(<AppShell />);

    expect(await screen.findByRole("heading", { name: "Task one draft" })).toBeTruthy();
    vi.mocked(api.updateDraft).mockClear();
    vi.useFakeTimers();

    act(() => {
      fireEvent.click(screen.getByText("Task Two"));
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(900);
    });

    expect(api.updateDraft).not.toHaveBeenCalledWith("task-2", "# Task one draft");

    await act(async () => {
      resolveTaskTwoDraft({ markdown: "# Task two draft" });
    });
    vi.useRealTimers();
    expect(await screen.findByRole("heading", { name: "Task two draft" })).toBeTruthy();
  });
});
