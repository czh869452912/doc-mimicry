import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../api";
import type { SessionRecord, TaskRecord, WorkspaceTree } from "../../types";
import { buildWorkspaceTreeData, latestByUpdatedAt, useWorkspaces } from "../state/useWorkspaces";

vi.mock("../../api", () => ({
  api: {
    listDocTypes: vi.fn(),
    listTasks: vi.fn(),
    listTaskSessions: vi.fn(),
    getWorkspace: vi.fn(),
    createTask: vi.fn(),
    createSession: vi.fn(),
  },
}));

function Harness({ onState }: { onState: (state: ReturnType<typeof useWorkspaces>) => void }) {
  const state = useWorkspaces();
  onState(state);
  return null;
}

describe("latestByUpdatedAt", () => {
  it("returns null for an empty list", () => {
    expect(latestByUpdatedAt([])).toBeNull();
  });

  it("returns the item with the newest updated_at timestamp", () => {
    const items = [
      { id: "old", updated_at: "2026-05-06T08:00:00Z" },
      { id: "new", updated_at: "2026-05-06T09:00:00Z" },
    ];

    expect(latestByUpdatedAt(items)?.id).toBe("new");
  });
});

describe("buildWorkspaceTreeData", () => {
  it("builds stable task, session, folder, and file node ids", () => {
    const task: TaskRecord = {
      id: "task-1",
      doc_type_id: "prd",
      brief: "Write a PRD",
      workspace_root: "workspace/task-1",
      created_at: "2026-05-06T08:00:00Z",
      updated_at: "2026-05-06T09:00:00Z",
    };
    const session: SessionRecord = {
      id: "session-1",
      task_id: "task-1",
      status: "draft_ready",
      created_at: "2026-05-06T08:00:00Z",
      updated_at: "2026-05-06T09:00:00Z",
    };
    const workspace: WorkspaceTree = {
      task_id: "task-1",
      root: "workspace/task-1",
      files: [{ path: "draft/draft.md", group: "draft", kind: "markdown" }],
    };

    const [node] = buildWorkspaceTreeData([task], { "task-1": [session] }, { "task-1": workspace });

    expect(node.id).toBe("task:task-1");
    expect(node.children?.some((child) => child.id === "session:session-1")).toBe(true);
    expect(node.children?.some((child) => child.id === "folder:task-1:draft")).toBe(true);
    const draftFolder = node.children?.find((child) => child.id === "folder:task-1:draft");
    expect(draftFolder?.children?.[0]?.id).toBe("file:task-1:draft/draft.md");
  });
});

describe("useWorkspaces initialization", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.clearAllMocks();
  });

  it("loads the initial workspace once without rerunning after active state is set", async () => {
    vi.mocked(api.listDocTypes).mockResolvedValue([{ id: "prd", title: "PRD", has_skill: true, resource_groups: {} }]);
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

    let latest!: ReturnType<typeof useWorkspaces>;
    render(<Harness onState={(state) => (latest = state)} />);

    await waitFor(() => expect(latest.loading).toBe(false));
    await new Promise((resolve) => window.setTimeout(resolve, 0));

    expect(api.listTasks).toHaveBeenCalledTimes(1);
    expect(api.listTaskSessions).toHaveBeenCalledTimes(2);
    expect(api.getWorkspace).toHaveBeenCalledTimes(1);
    expect(latest.activeTask?.id).toBe("task-1");
    expect(latest.activeSession?.id).toBe("session-1");
  });
});
