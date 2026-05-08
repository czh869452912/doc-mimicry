import { useNavigate, useSearch } from "@tanstack/react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef } from "react";
import { api } from "../../api";
import type { SessionRecord, TaskRecord } from "../../types";
import { useDocTypes } from "./useDocTypes";
import { useSessions } from "./useSessions";
import { useTasks } from "./useTasks";

const LAST_TASK_KEY = "docagent:lastTaskId";
const LAST_SESSION_KEY = "docagent:lastSessionId";

export function isRunnableSession(session: SessionRecord): boolean {
  return !["cancelled", "completed", "failed"].includes(session.status);
}

function latestByUpdatedAt<T extends { updated_at: string }>(items: T[]): T | null {
  return [...items].sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at))[0] ?? null;
}

export function useActiveWorkspace() {
  const navigate = useNavigate({ from: "/" });
  const search = useSearch({ from: "/" });
  const queryClient = useQueryClient();

  const docTypesQuery = useDocTypes();
  const tasksQuery = useTasks();
  const tasks = tasksQuery.data ?? [];

  // Active task: resolved from URL param, else null
  const activeTask = tasks.find((t) => t.id === search.task) ?? null;

  const sessionsQuery = useSessions(activeTask?.id);
  const sessions = sessionsQuery.data ?? [];

  // Active session: resolved from URL param, then latest
  const activeSession =
    sessions.find((s) => s.id === search.session) ?? latestByUpdatedAt(sessions) ?? null;

  // Sync URL when session resolves to a default (no explicit URL param)
  useEffect(() => {
    if (!activeSession || activeSession.id === search.session) return;
    void navigate({ search: (prev) => ({ ...prev, session: activeSession.id }), replace: true });
  }, [activeSession?.id, search.session, navigate]);

  // On first load: if no task URL param, navigate to best task from localStorage/latest
  const initialized = useRef(false);
  useEffect(() => {
    if (tasksQuery.isLoading || initialized.current) return;
    initialized.current = true;
    if (!search.task && tasks.length > 0) {
      const remembered = window.localStorage.getItem(LAST_TASK_KEY);
      const task = tasks.find((t) => t.id === remembered) ?? latestByUpdatedAt(tasks);
      if (task) {
        void navigate({ search: { task: task.id }, replace: true });
      }
    }
  }, [tasksQuery.isLoading, tasks, search.task, navigate]);

  const selectTask = useCallback(
    (task: TaskRecord) => {
      window.localStorage.setItem(LAST_TASK_KEY, task.id);
      window.localStorage.removeItem(LAST_SESSION_KEY);
      void navigate({ search: { task: task.id }, replace: true });
    },
    [navigate],
  );

  const selectSession = useCallback(
    (session: SessionRecord) => {
      window.localStorage.setItem(LAST_SESSION_KEY, session.id);
      void navigate({ search: (prev) => ({ ...prev, session: session.id }), replace: true });
    },
    [navigate],
  );

  const createWorkspaceMutation = useMutation({
    mutationFn: async ({ docTypeId, input }: { docTypeId: string; input: { title: string; description: string } }) => {
      const task = await api.createTask(docTypeId, input);
      const session = await api.createSession(task.id);
      return { task, session };
    },
    onSuccess: ({ task, session }) => {
      window.localStorage.setItem(LAST_TASK_KEY, task.id);
      window.localStorage.setItem(LAST_SESSION_KEY, session.id);
      void queryClient.invalidateQueries({ queryKey: ["tasks"] });
      void navigate({ search: { task: task.id, session: session.id }, replace: true });
    },
  });

  const createSessionMutation = useMutation({
    mutationFn: async () => {
      if (!activeTask) throw new Error("No active task");
      return api.createSession(activeTask.id);
    },
    onSuccess: (session) => {
      window.localStorage.setItem(LAST_SESSION_KEY, session.id);
      void queryClient.invalidateQueries({ queryKey: ["sessions", activeTask?.id] });
      void navigate({ search: (prev) => ({ ...prev, session: session.id }), replace: true });
    },
  });

  const ensureSession = useCallback(async (): Promise<SessionRecord | null> => {
    if (!activeTask) return null;
    if (activeSession && isRunnableSession(activeSession)) return activeSession;
    return createSessionMutation.mutateAsync();
  }, [activeTask, activeSession, createSessionMutation]);

  const loading = tasksQuery.isLoading || sessionsQuery.isLoading;
  const error = tasksQuery.error?.message ?? sessionsQuery.error?.message ?? null;

  return {
    activeSession,
    activeTask,
    createWorkspace: (docTypeId: string, input: { title: string; description: string }) =>
      createWorkspaceMutation.mutateAsync({ docTypeId, input }),
    createSessionForActiveTask: () => createSessionMutation.mutateAsync(),
    docTypes: docTypesQuery.data ?? [],
    ensureSession,
    error,
    loading,
    selectSession,
    selectTask,
    sessions,
    tasks,
  };
}
