import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import type { DocTypeSummary, SessionRecord, TaskRecord, WorkspaceFile, WorkspaceTree } from "../../types";

const LAST_TASK_KEY = "docagent:lastTaskId";
const LAST_SESSION_KEY = "docagent:lastSessionId";
const WORKSPACE_FOLDERS = ["versions", "inputs", "context", "draft", "reviews", "artifacts"] as const;

export type WorkspaceTreeNodeKind = "task" | "session" | "folder" | "file";

export interface WorkspaceTreeNode {
  id: string;
  name: string;
  kind: WorkspaceTreeNodeKind;
  taskId?: string;
  sessionId?: string;
  path?: string;
  status?: string;
  children?: WorkspaceTreeNode[];
}

export function latestByUpdatedAt<T extends { updated_at: string }>(items: T[]): T | null {
  return [...items].sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at))[0] ?? null;
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
    const sessions = [...(sessionsByTaskId[task.id] ?? [])].sort(
      (left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at),
    );
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
      name: task.brief,
      kind: "task" as const,
      taskId: task.id,
      children: [
        ...sessions.map((session) => ({
          id: `session:${session.id}`,
          name: `#${session.id.slice(0, 8)} · ${session.status}`,
          kind: "session" as const,
          taskId: task.id,
          sessionId: session.id,
          status: session.status,
        })),
        ...folderNodes,
      ],
    };
  });
}

function fileToTreeNode(taskId: string, file: WorkspaceFile): WorkspaceTreeNode {
  const name = file.path.split("/").at(-1) ?? file.path;
  return {
    id: `file:${taskId}:${file.path}`,
    name,
    kind: "file",
    taskId,
    path: file.path,
  };
}

export function useWorkspaces() {
  const [docTypes, setDocTypes] = useState<DocTypeSummary[]>([]);
  const [tasks, setTasks] = useState<TaskRecord[]>([]);
  const [sessions, setSessions] = useState<SessionRecord[]>([]);
  const [workspaceTree, setWorkspaceTree] = useState<WorkspaceTree | null>(null);
  const [activeTask, setActiveTask] = useState<TaskRecord | null>(null);
  const [activeSession, setActiveSession] = useState<SessionRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshActiveWorkspace = useCallback(
    async (taskOverride: TaskRecord | null = activeTask, sessionOverride: SessionRecord | null = activeSession) => {
      if (!taskOverride) {
        setWorkspaceTree(null);
        setSessions([]);
        setActiveSession(null);
        return;
      }

      const [nextSessions, nextWorkspace] = await Promise.all([
        api.listTaskSessions(taskOverride.id),
        api.getWorkspace(taskOverride.id),
      ]);
      const preferredSession =
        (sessionOverride && nextSessions.find((session) => session.id === sessionOverride.id)) ??
        latestByUpdatedAt(nextSessions);

      setSessions(nextSessions);
      setWorkspaceTree(nextWorkspace);
      setActiveSession(preferredSession);
      window.localStorage.setItem(LAST_TASK_KEY, taskOverride.id);
      if (preferredSession) {
        window.localStorage.setItem(LAST_SESSION_KEY, preferredSession.id);
      }
    },
    [activeSession, activeTask],
  );

  const selectTask = useCallback(
    async (task: TaskRecord) => {
      setActiveTask(task);
      await refreshActiveWorkspace(task, null);
    },
    [refreshActiveWorkspace],
  );

  const selectSession = useCallback(
    async (session: SessionRecord) => {
      setActiveSession(session);
      window.localStorage.setItem(LAST_SESSION_KEY, session.id);
    },
    [],
  );

  const loadInitialState = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextDocTypes, nextTasks] = await Promise.all([api.listDocTypes(), api.listTasks()]);
      setDocTypes(nextDocTypes);
      setTasks(nextTasks);

      const rememberedTaskId = window.localStorage.getItem(LAST_TASK_KEY);
      const nextTask = nextTasks.find((task) => task.id === rememberedTaskId) ?? latestByUpdatedAt(nextTasks);
      if (nextTask) {
        setActiveTask(nextTask);
        const nextSessions = await api.listTaskSessions(nextTask.id);
        const rememberedSessionId = window.localStorage.getItem(LAST_SESSION_KEY);
        const nextSession =
          nextSessions.find((session) => session.id === rememberedSessionId) ?? latestByUpdatedAt(nextSessions);
        await refreshActiveWorkspace(nextTask, nextSession);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load workspaces");
    } finally {
      setLoading(false);
    }
  }, [refreshActiveWorkspace]);

  useEffect(() => {
    void loadInitialState();
  }, [loadInitialState]);

  const createWorkspace = useCallback(
    async (docTypeId: string, brief: string) => {
      const task = await api.createTask(docTypeId, brief);
      const session = await api.createSession(task.id);
      const nextTasks = await api.listTasks();
      setTasks(nextTasks);
      setActiveTask(task);
      setActiveSession(session);
      await refreshActiveWorkspace(task, session);
      return { task, session };
    },
    [refreshActiveWorkspace],
  );

  const ensureSession = useCallback(async () => {
    if (!activeTask) return null;
    if (activeSession && isRunnableSession(activeSession)) return activeSession;
    const session = await api.createSession(activeTask.id);
    await refreshActiveWorkspace(activeTask, session);
    return session;
  }, [activeSession, activeTask, refreshActiveWorkspace]);

  const treeData = useMemo(
    () =>
      buildWorkspaceTreeData(
        tasks,
        activeTask ? { [activeTask.id]: sessions } : {},
        activeTask && workspaceTree ? { [activeTask.id]: workspaceTree } : {},
      ),
    [activeTask, sessions, tasks, workspaceTree],
  );

  return {
    activeSession,
    activeTask,
    createWorkspace,
    docTypes,
    ensureSession,
    error,
    loading,
    refreshActiveWorkspace,
    selectSession,
    selectTask,
    sessions,
    tasks,
    treeData,
    workspaceTree,
  };
}
