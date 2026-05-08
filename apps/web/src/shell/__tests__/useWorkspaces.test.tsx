import { describe, expect, it } from "vitest";
import type { SessionRecord, TaskRecord, WorkspaceTree } from "../../types";
import { buildWorkspaceTreeData, latestByUpdatedAt } from "../state/useWorkspaces";

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
      title: "Billing PRD",
      description: "Write a PRD",
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
    expect(node.name).toBe("Billing PRD");
    expect(node.children?.some((child) => child.id === "folder:task-1:draft")).toBe(true);
    expect(node.children?.every((child) => (child.kind as string) !== "session")).toBe(true);
    const draftFolder = node.children?.find((child) => child.id === "folder:task-1:draft");
    expect(draftFolder?.children?.[0]?.id).toBe("file:task-1:draft/draft.md");
  });
});
