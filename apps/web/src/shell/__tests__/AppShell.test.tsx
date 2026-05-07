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
        title: "Restored workspace",
        description: "Write a PRD",
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
    vi.mocked(api.sendMessage).mockResolvedValue({ accepted: true, status: "running_revision" });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("loads the active task draft after restored workspace state is available", async () => {
    render(<AppShell />);

    await waitFor(() => expect(api.getDraft).toHaveBeenCalledWith("task-1"));
    expect(await screen.findByRole("heading", { name: "Restored draft" })).toBeTruthy();
    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 900));
    });
    expect(api.updateDraft).not.toHaveBeenCalled();
  });

  it("runs slash commands selected from the command palette", async () => {
    render(<AppShell />);

    await screen.findByText("Restored workspace");
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
        title: "Task One",
        description: "Task one description",
        workspace_root: "workspace/task-1",
        created_at: "2026-05-06T08:00:00Z",
        updated_at: "2026-05-06T09:00:00Z",
      },
      {
        id: "task-2",
        doc_type_id: "prd",
        brief: "Task Two",
        title: "Task Two",
        description: "Task two description",
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

  it("creates a workspace with a separate title and description using loaded document types", async () => {
    vi.mocked(api.listDocTypes).mockResolvedValue([
      { id: "proposal", title: "Proposal", has_skill: true, resource_groups: {} },
    ]);
    vi.mocked(api.listTasks).mockResolvedValue([]);
    vi.mocked(api.listTaskSessions).mockResolvedValue([]);
    vi.mocked(api.createTask).mockResolvedValue({
      id: "task-2",
      doc_type_id: "proposal",
      brief: "Detailed opportunity description",
      title: "Opportunity proposal",
      description: "Detailed opportunity description",
      workspace_root: "workspace/task-2",
      created_at: "2026-05-06T10:00:00Z",
      updated_at: "2026-05-06T10:00:00Z",
    });
    vi.mocked(api.createSession).mockResolvedValue({
      id: "session-2",
      task_id: "task-2",
      status: "idle",
      created_at: "2026-05-06T10:00:00Z",
      updated_at: "2026-05-06T10:00:00Z",
    });

    render(<AppShell />);

    await userEvent.click(await screen.findByRole("button", { name: /create workspace/i }));
    await userEvent.clear(screen.getByLabelText("Title"));
    await userEvent.type(screen.getByLabelText("Title"), "Opportunity proposal");
    await userEvent.clear(screen.getByLabelText("Description"));
    await userEvent.type(screen.getByLabelText("Description"), "Detailed opportunity description");
    await userEvent.click(screen.getAllByRole("button", { name: /create workspace/i })[1]);

    await waitFor(() =>
      expect(api.createTask).toHaveBeenCalledWith("proposal", {
        title: "Opportunity proposal",
        description: "Detailed opportunity description",
      }),
    );
  });

  it("creates a new session under the active workspace", async () => {
    vi.mocked(api.createSession).mockResolvedValue({
      id: "session-2",
      task_id: "task-1",
      status: "idle",
      created_at: "2026-05-06T10:00:00Z",
      updated_at: "2026-05-06T10:00:00Z",
    });
    vi.mocked(api.listTaskSessions).mockResolvedValueOnce([
      {
        id: "session-1",
        task_id: "task-1",
        status: "draft_ready",
        created_at: "2026-05-06T08:00:00Z",
        updated_at: "2026-05-06T09:00:00Z",
      },
    ]).mockResolvedValue([
      {
        id: "session-1",
        task_id: "task-1",
        status: "draft_ready",
        created_at: "2026-05-06T08:00:00Z",
        updated_at: "2026-05-06T09:00:00Z",
      },
      {
        id: "session-2",
        task_id: "task-1",
        status: "idle",
        created_at: "2026-05-06T10:00:00Z",
        updated_at: "2026-05-06T10:00:00Z",
      },
    ]);

    render(<AppShell />);

    await userEvent.click(await screen.findByRole("button", { name: /new session/i }));

    await waitFor(() => expect(api.createSession).toHaveBeenCalledWith("task-1"));
    expect(await screen.findByText(/session-2/)).toBeTruthy();
  });

  it("opens settings and shows document type resources", async () => {
    vi.mocked(api.listDocTypes).mockResolvedValue([
      {
        id: "prd",
        title: "PRD",
        has_skill: true,
        resource_groups: { examples: ["examples/enterprise-prd.md"] },
        skill_markdown: "# PRD skill",
      },
    ]);

    render(<AppShell />);

    await userEvent.click(await screen.findByRole("button", { name: /open settings/i }));

    expect(await screen.findByRole("heading", { name: "Settings" })).toBeTruthy();
    expect(await screen.findByText("examples/enterprise-prd.md")).toBeTruthy();
  });

  it("loads the source editor only when source mode is selected", async () => {
    render(<AppShell />);

    await screen.findByRole("heading", { name: "Restored draft" });
    await userEvent.click(screen.getByRole("button", { name: "Source" }));

    expect(await screen.findByRole("textbox")).toBeTruthy();
  });

  it("sends chat messages in background mode and refreshes timeline immediately", async () => {
    render(<AppShell />);

    await screen.findByText("Restored workspace");
    vi.mocked(api.getWorkspace).mockClear();
    vi.mocked(api.getTimeline).mockClear();

    await userEvent.type(screen.getByLabelText("Message"), "Revise the draft");
    await userEvent.keyboard("{Enter}");

    await waitFor(() => expect(api.sendMessage).toHaveBeenCalledWith("session-1", "Revise the draft"));
    expect(api.getTimeline).toHaveBeenCalledWith("session-1");
    expect(api.getWorkspace).not.toHaveBeenCalled();
    expect(await screen.findByText("Working...")).toBeTruthy();
  });
});
