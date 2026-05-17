import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../../api";
import type { AcpEvent } from "../../../types";
import { ConversationPane } from "../ConversationPane";

vi.mock("../../../api", () => ({
  API_BASE: "http://127.0.0.1:8000",
  api: {
    answerPermission: vi.fn(),
    cancelSession: vi.fn(),
    exportDocx: vi.fn(),
    exportPdf: vi.fn(),
    importFileInput: vi.fn(),
    sendMessage: vi.fn(),
    startLoop: vi.fn(),
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

const events: AcpEvent[] = [
  {
    id: "evt-user",
    session_id: "session-1",
    sequence: 1,
    event_type: "docagent/prompt",
    payload: { prompt: "Write a launch PRD" },
    projection: {},
    created_at: "2026-05-15T00:00:00Z",
  },
];

function renderPane(overrides: Partial<React.ComponentProps<typeof ConversationPane>> = {}) {
  return render(
    <ConversationPane
      activeSession={session}
      activeTask={task}
      createSession={vi.fn().mockResolvedValue(session)}
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
    vi.unstubAllEnvs();
  });

  it("renders the center pane through the ACP interaction surface", () => {
    const { container } = renderPane();

    expect(container.querySelector(".acp-thread")).toBeTruthy();
    expect(container.querySelector(".acp-composer")).toBeTruthy();
    expect(screen.getByRole("button", { name: /copy text/i })).toBeTruthy();
    expect(container.querySelector(".conversation-stream")).toBeFalsy();
    expect(screen.getByText("Write a launch PRD")).toBeTruthy();
  });

  it("can replace the local center pane with an external ACP UI iframe", async () => {
    vi.stubEnv("VITE_ACP_UI_URL", "http://127.0.0.1:4173/acp-ui/");
    const { container } = renderPane();

    const frame = screen.getByTitle("ACP interaction client") as HTMLIFrameElement;
    expect(frame).toBeTruthy();
    expect(frame.src).toContain("docagentSessionId=session-1");
    expect(frame.src).toContain("docagentWorkspaceRoot=workspace%2Ftask-1");
    expect(container.querySelector(".acp-thread")).toBeFalsy();
    vi.unstubAllEnvs();
  });

  it("renders running status inside the ACP thread", () => {
    render(
      <ConversationPane
        activeSession={{ ...session, status: "running_chat" }}
        activeTask={task}
        createSession={vi.fn().mockResolvedValue(session)}
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

  it("refreshes workspace when the ACP surface imports composer attachments", async () => {
    const user = userEvent.setup();
    const refreshWorkspace = vi.fn().mockResolvedValue(undefined);
    vi.mocked(api.importFileInput).mockResolvedValue({
      id: "input-1",
      status: "converted",
      source_path: "inputs/original/context.txt",
      markdown_path: "inputs/markdown/context.md",
      conversion_report_path: "inputs/reports/context.json",
      original_filename: "context.txt",
      created_at: "2026-05-15T00:00:00Z",
    });
    vi.mocked(api.sendMessage).mockResolvedValue({ session_id: "session-1", accepted: true, status: "running_chat" });
    renderPane({ refreshWorkspace });

    await user.upload(
      document.querySelector('input[type="file"]') as HTMLInputElement,
      new File(["Attachment context"], "context.txt", { type: "text/plain" }),
    );
    await user.type(screen.getByLabelText("Message"), "Use context");
    await user.keyboard("{Enter}");

    await waitFor(() => expect(api.sendMessage).toHaveBeenCalledWith(
      "session-1",
      "Use context",
      [
        {
          name: "context.txt",
          markdown_path: "inputs/markdown/context.md",
          source_path: "inputs/original/context.txt",
          conversion_report_path: "inputs/reports/context.json",
        },
      ],
    ));
    expect(refreshWorkspace.mock.invocationCallOrder[0]).toBeLessThan(
      vi.mocked(api.sendMessage).mock.invocationCallOrder[0],
    );
  });

  it("answers ACP permission requests through the backend gateway", async () => {
    const user = userEvent.setup();
    const refreshTimeline = vi.fn().mockResolvedValue(undefined);
    const refreshSessions = vi.fn().mockResolvedValue(undefined);
    vi.mocked(api.answerPermission).mockResolvedValue({ session_id: "session-1", accepted: true, status: "idle" });
    renderPane({
      events: [
        {
          id: "permission-event",
          session_id: "session-1",
          sequence: 1,
          event_type: "permission/request",
          payload: { request_id: "permission-1", message: "Allow file write?" },
          projection: {},
          created_at: "2026-05-15T00:00:00Z",
        },
      ],
      refreshTimeline,
      refreshSessions,
    });

    await user.click(screen.getByRole("button", { name: /allow permission request/i }));

    expect(api.answerPermission).toHaveBeenCalledWith("session-1", "permission-1", "allow");
    expect(refreshTimeline).toHaveBeenCalledOnce();
    expect(refreshSessions).toHaveBeenCalledOnce();
  });

  it("allows chat from an outline-approval session", async () => {
    vi.mocked(api.sendMessage).mockResolvedValue({ session_id: "session-1", accepted: true, status: "running_chat" });
    renderPane({ activeSession: { ...session, status: "await_outline_approval" } });

    await userEvent.type(screen.getByLabelText("Message"), "Adjust the outline");
    await userEvent.keyboard("{Enter}");

    expect(api.sendMessage).toHaveBeenCalledWith("session-1", "Adjust the outline", []);
  });

  it("refreshes sessions immediately after a slash command starts a background operation", async () => {
    const refreshSessions = vi.fn().mockResolvedValue(undefined);
    const refreshTimeline = vi.fn().mockResolvedValue(undefined);
    const refreshWorkspace = vi.fn().mockResolvedValue(undefined);
    vi.mocked(api.startLoop).mockResolvedValue({ session_id: "session-1", accepted: true, status: "running_context" });
    renderPane({
      activeSession: { ...session, status: "idle" },
      refreshSessions,
      refreshTimeline,
      refreshWorkspace,
    });

    await userEvent.type(screen.getByLabelText("Message"), "/start");
    await userEvent.keyboard("{Enter}");

    expect(api.startLoop).toHaveBeenCalledWith("session-1");
    expect(refreshSessions).toHaveBeenCalledOnce();
    expect(refreshTimeline).toHaveBeenCalledOnce();
    expect(refreshWorkspace).toHaveBeenCalledOnce();
  });

  it("starts the outline loop in a fresh session when the current session is not idle", async () => {
    const freshSession = { ...session, id: "session-fresh", status: "idle" };
    const createSession = vi.fn().mockResolvedValue(freshSession);
    vi.mocked(api.startLoop).mockResolvedValue({ session_id: "session-fresh", accepted: true, status: "running_context" });
    renderPane({ activeSession: { ...session, status: "draft_ready" }, createSession });

    await userEvent.type(screen.getByLabelText("Message"), "/start");
    await userEvent.keyboard("{Enter}");

    expect(createSession).toHaveBeenCalledOnce();
    expect(api.startLoop).toHaveBeenCalledWith("session-fresh");
  });

  it("does not submit or cancel when Enter is pressed while running", async () => {
    renderPane({ activeSession: { ...session, status: "running_chat" } });

    await userEvent.type(screen.getByLabelText("Message"), "Do not cancel");
    await userEvent.keyboard("{Enter}");

    expect(api.cancelSession).not.toHaveBeenCalled();
    expect(api.sendMessage).not.toHaveBeenCalled();
  });

  it("sends only one cancel request while cancellation is already in flight", async () => {
    const user = userEvent.setup();
    let resolveCancel!: (value: { session_id: string; status: string }) => void;
    vi.mocked(api.cancelSession).mockReturnValue(
      new Promise((resolve) => {
        resolveCancel = resolve;
      }) as ReturnType<typeof api.cancelSession>,
    );

    renderPane({ activeSession: { ...session, status: "running_chat" } });

    const stopButton = screen.getByRole("button", { name: /stop the running agent/i });
    await user.dblClick(stopButton);

    expect(api.cancelSession).toHaveBeenCalledTimes(1);

    resolveCancel({ session_id: "session-1", status: "cancelled" });
  });
});
