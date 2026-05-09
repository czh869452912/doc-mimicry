import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../api";
import { createAppRouter } from "../../App";
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
    importTextInput: vi.fn(),
    listDocTypes: vi.fn(),
    listTaskSessions: vi.fn(),
    listTasks: vi.fn(),
    runChecklist: vi.fn(),
    reviseSelection: vi.fn(),
    sendMessage: vi.fn(),
    startLoop: vi.fn(),
    updateDraft: vi.fn(),
  },
}));

vi.mock("../editor/LazyDraftEditor", () => ({
  LazyDraftEditor: ({ onSelection }: { onSelection: (selectedText: string) => void }) => (
    <div data-testid="draft-source-editor" onClick={() => onSelection("selected paragraph")} />
  ),
}));

vi.mock("react-resizable-panels", () => ({
  Group: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Panel: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Separator: () => <div />,
}));

function renderAppShell(initialUrl = "/") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createAppRouter(createMemoryHistory({ initialEntries: [initialUrl] }));
  return {
    ...render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    ),
    router,
  };
}

// AppShell is not imported directly in these tests — it is rendered via the router.
void AppShell;

describe("AppShell", () => {
  beforeEach(() => {
    class ResizeObserverStub {
      disconnect() {}
      observe() {}
      unobserve() {}
    }

    vi.stubGlobal("ResizeObserver", ResizeObserverStub);
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
    window.HTMLElement.prototype.scrollTo = vi.fn();
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
    vi.mocked(api.importTextInput).mockResolvedValue({
      id: "input-scope-notes",
      status: "converted",
      source_path: "inputs/original/scope-notes.txt",
      markdown_path: "inputs/markdown/scope-notes.md",
      conversion_report_path: "inputs/reports/scope-notes.json",
      original_filename: "scope-notes.md",
      created_at: "2026-05-08T00:00:00Z",
    });
    vi.mocked(api.updateDraft).mockResolvedValue({ markdown: "# Restored draft" });
    vi.mocked(api.sendMessage).mockResolvedValue({ session_id: "session-1", accepted: true, status: "running_revision" });
    vi.mocked(api.reviseSelection).mockResolvedValue({ session_id: "session-1", next_state: "RUNNING_REVISION" });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("loads the active task draft after restored workspace state is available", async () => {
    renderAppShell("/?task=task-1&session=session-1");

    await waitFor(() => expect(api.getDraft).toHaveBeenCalledWith("task-1"));
    expect(await screen.findByRole("heading", { name: "Restored draft" })).toBeTruthy();
    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 900));
    });
    expect(api.updateDraft).not.toHaveBeenCalled();
  });

  it("runs slash commands selected from the command palette", async () => {
    renderAppShell("/?task=task-1&session=session-1");

    await screen.findByText("Restored workspace");
    await userEvent.click(screen.getByText("Ctrl+Shift+P"));
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

    renderAppShell("/?task=task-1&session=session-1");

    expect(await screen.findByRole("heading", { name: "Task one draft" })).toBeTruthy();
    vi.mocked(api.updateDraft).mockClear();

    fireEvent.click(screen.getByText("Task Two"));

    // Wait for the query to fire so resolveTaskTwoDraft is initialized
    await waitFor(() => expect(api.getDraft).toHaveBeenCalledWith("task-2"));

    // The key invariant: task-1 draft must NOT be auto-saved into task-2
    expect(api.updateDraft).not.toHaveBeenCalledWith("task-2", "# Task one draft");

    resolveTaskTwoDraft({ markdown: "# Task two draft" });
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

    renderAppShell();

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

    renderAppShell("/?task=task-1&session=session-1");

    await userEvent.click(await screen.findByRole("button", { name: /new session/i }));

    await waitFor(() => expect(api.createSession).toHaveBeenCalledWith("task-1"));
    expect(await screen.findByText(/session-2/)).toBeTruthy();
  });

  it("restores task and session from URL search params", async () => {
    vi.mocked(api.listTasks).mockResolvedValue([
      {
        id: "task-1",
        doc_type_id: "prd",
        brief: "Older task",
        title: "Older task",
        description: "Older task",
        workspace_root: "workspace/task-1",
        created_at: "2026-05-06T08:00:00Z",
        updated_at: "2026-05-06T08:00:00Z",
      },
      {
        id: "task-2",
        doc_type_id: "prd",
        brief: "Linked task",
        title: "Linked task",
        description: "Linked task",
        workspace_root: "workspace/task-2",
        created_at: "2026-05-06T08:00:00Z",
        updated_at: "2026-05-06T09:00:00Z",
      },
    ]);
    vi.mocked(api.listTaskSessions).mockImplementation((taskId) =>
      Promise.resolve(
        taskId === "task-2"
          ? [
              {
                id: "session-2",
                task_id: "task-2",
                status: "draft_ready",
                created_at: "2026-05-06T09:00:00Z",
                updated_at: "2026-05-06T09:00:00Z",
              },
            ]
          : [],
      ),
    );
    vi.mocked(api.getWorkspace).mockResolvedValue({ task_id: "task-2", root: "workspace/task-2", files: [] });
    vi.mocked(api.getDraft).mockResolvedValue({ markdown: "# Linked draft" });

    renderAppShell("/?task=task-2&session=session-2");

    expect(await screen.findByText("Linked task")).toBeTruthy();
    expect(await screen.findByRole("heading", { name: "Linked draft" })).toBeTruthy();
    await waitFor(() => expect(api.listTaskSessions).toHaveBeenCalledWith("task-2"));
  });

  it("syncs selected task and session into URL search params", async () => {
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
    vi.mocked(api.listTaskSessions).mockImplementation((taskId) =>
      Promise.resolve(
        taskId === "task-2"
          ? [
              {
                id: "session-2",
                task_id: "task-2",
                status: "idle",
                created_at: "2026-05-06T10:00:00Z",
                updated_at: "2026-05-06T10:00:00Z",
              },
            ]
          : [
              {
                id: "session-1",
                task_id: "task-1",
                status: "draft_ready",
                created_at: "2026-05-06T08:00:00Z",
                updated_at: "2026-05-06T09:00:00Z",
              },
            ],
      ),
    );
    vi.mocked(api.getWorkspace).mockImplementation((taskId) =>
      Promise.resolve({ task_id: taskId, root: `workspace/${taskId}`, files: [] }),
    );
    vi.mocked(api.getDraft).mockResolvedValue({ markdown: "# Draft" });
    window.localStorage.setItem("docagent:lastTaskId", "task-1");

    const { router } = renderAppShell();

    await screen.findByText("Task One");
    fireEvent.click(screen.getByText("Task Two"));

    await waitFor(() => {
      const search = router.state.location.search as { task?: string; session?: string };
      expect(search.task).toBe("task-2");
      expect(search.session).toBe("session-2");
    });
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

    renderAppShell("/?task=task-1&session=session-1");

    await userEvent.click(await screen.findByRole("button", { name: /open settings/i }));

    expect(await screen.findByRole("heading", { name: "Settings" })).toBeTruthy();
    expect(await screen.findByText("examples/enterprise-prd.md")).toBeTruthy();
  });

  it("loads the source editor only when source mode is selected", async () => {
    renderAppShell("/?task=task-1&session=session-1");

    await screen.findByRole("heading", { name: "Restored draft" });
    await userEvent.click(screen.getByRole("button", { name: "Source" }));

    expect(await screen.findByRole("textbox")).toBeTruthy();
  });

  it("queues selected draft text into the assistant composer", async () => {
    renderAppShell("/?task=task-1&session=session-1");

    await screen.findByRole("heading", { name: "Restored draft" });
    await userEvent.click(screen.getByRole("button", { name: "Source" }));
    await userEvent.click(await screen.findByTestId("draft-source-editor"));
    await userEvent.click(screen.getByRole("button", { name: "Send to chat" }));

    expect(await screen.findByDisplayValue(/selected paragraph/)).toBeTruthy();
  });

  it("revises selected draft text through the active session", async () => {
    renderAppShell("/?task=task-1&session=session-1");

    await screen.findByRole("heading", { name: "Restored draft" });
    await userEvent.click(screen.getByRole("button", { name: "Source" }));
    await userEvent.click(await screen.findByTestId("draft-source-editor"));
    await userEvent.click(screen.getByRole("button", { name: "Revise selection" }));

    await waitFor(() =>
      expect(api.reviseSelection).toHaveBeenCalledWith(
        "session-1",
        "selected paragraph",
        "Please revise the selected passage while preserving its meaning.",
      ),
    );
    expect(api.getTimeline).toHaveBeenCalledWith("session-1");
    expect(api.getWorkspace).toHaveBeenCalledWith("task-1");
  });

  it("sends chat messages in background mode and refreshes timeline and workspace", async () => {
    renderAppShell("/?task=task-1&session=session-1");

    await screen.findByText("Restored workspace");
    vi.mocked(api.getWorkspace).mockClear();
    vi.mocked(api.getTimeline).mockClear();

    await userEvent.type(screen.getByLabelText("Message"), "Revise the draft");
    await userEvent.keyboard("{Enter}");

    await waitFor(() => expect(api.sendMessage).toHaveBeenCalledWith("session-1", "Revise the draft"));
    expect(api.getTimeline).toHaveBeenCalledWith("session-1");
    expect(api.getWorkspace).toHaveBeenCalledWith("task-1");
    expect(screen.queryByText("Working...")).toBeNull();
  });

  it("imports composer text attachments before sending the message", async () => {
    renderAppShell("/?task=task-1&session=session-1");

    await screen.findByText("Restored workspace");
    await userEvent.click(screen.getByLabelText("Attach file"));
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    expect(fileInput).toBeTruthy();
    await userEvent.upload(fileInput, new File(["Attachment context"], "scope-notes.md", { type: "text/markdown" }));
    expect(await screen.findByText("scope-notes.md")).toBeTruthy();

    await userEvent.type(screen.getByLabelText("Message"), "Use the attached notes");
    await userEvent.keyboard("{Enter}");

    await waitFor(() =>
      expect(api.importTextInput).toHaveBeenCalledWith("task-1", "scope-notes.md", "Attachment context"),
    );
    await waitFor(() =>
      expect(api.sendMessage).toHaveBeenCalledWith(
        "session-1",
        "Use the attached notes\nImported attachment scope-notes.md as inputs/markdown/scope-notes.md.",
      ),
    );
  });

  it("reloads an assistant message by resending the nearest previous user message", async () => {
    vi.mocked(api.getTimeline).mockResolvedValue([
      {
        id: "user-1",
        actor: "user",
        kind: "user_message",
        raw_event_id: null,
        session_id: "session-1",
        summary: "Revise the launch scope",
        paths: [],
        status: "succeeded",
        task_id: "task-1",
      },
      {
        id: "agent-1",
        actor: "agent",
        kind: "agent_message",
        raw_event_id: null,
        session_id: "session-1",
        summary: "I updated the launch scope.",
        paths: [],
        status: "succeeded",
        task_id: "task-1",
      },
    ]);

    renderAppShell("/?task=task-1&session=session-1");

    await screen.findByText("I updated the launch scope.");
    vi.mocked(api.sendMessage).mockClear();
    vi.mocked(api.getTimeline).mockClear();

    const reloadButton = screen.getByRole("button", { name: /reload response/i });
    expect(reloadButton.hasAttribute("disabled")).toBe(false);
    fireEvent.click(reloadButton);

    await waitFor(() => expect(api.sendMessage).toHaveBeenCalledWith("session-1", "Revise the launch scope"));
    expect(api.getTimeline).toHaveBeenCalledWith("session-1");
  });
});
