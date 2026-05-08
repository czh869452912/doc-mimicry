// This file retains only the pure helper functions and types used by AppShell, WorkspacePane,
// and existing tests. The useWorkspaces hook has been replaced by useActiveWorkspace + individual
// Query hooks.

import type { SessionRecord, TaskRecord, WorkspaceFile, WorkspaceTree } from "../../types";

export type WorkspaceTreeNodeKind = "task" | "folder" | "file";

export interface WorkspaceTreeNode {
  id: string;
  name: string;
  kind: WorkspaceTreeNodeKind;
  taskId?: string;
  path?: string;
  children?: WorkspaceTreeNode[];
}

export interface CreateWorkspaceInput {
  description: string;
  title: string;
}

const WORKSPACE_FOLDERS = ["versions", "inputs", "context", "draft", "reviews", "artifacts"] as const;

export function latestByUpdatedAt<T extends { updated_at: string }>(items: T[]): T | null {
  return [...items].sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at))[0] ?? null;
}

export function isRunnableSession(session: SessionRecord): boolean {
  return !["cancelled", "completed", "failed"].includes(session.status);
}

export function buildWorkspaceTreeData(
  tasks: TaskRecord[],
  sessionsByTaskId: Record<string, SessionRecord[]>,
  workspaceByTaskId: Record<string, WorkspaceTree | undefined>,
): WorkspaceTreeNode[] {
  return tasks.map((task) => {
    const files = workspaceByTaskId[task.id]?.files ?? [];
    const folderNodes = WORKSPACE_FOLDERS.map((folder) => ({
      id: `folder:${task.id}:${folder}`,
      name: `${folder}/`,
      kind: "folder" as const,
      taskId: task.id,
      path: folder,
      children: files
        .filter((file) => file.path === folder || file.path.startsWith(`${folder}/`))
        .map((file) => fileToTreeNode(task.id, file)),
    }));
    return {
      id: `task:${task.id}`,
      name: task.title ?? task.brief,
      kind: "task" as const,
      taskId: task.id,
      children: [...folderNodes],
    };
  });
}

function fileToTreeNode(taskId: string, file: WorkspaceFile): WorkspaceTreeNode {
  const name = file.path.split("/").at(-1) ?? file.path;
  return { id: `file:${taskId}:${file.path}`, name, kind: "file", taskId, path: file.path };
}
