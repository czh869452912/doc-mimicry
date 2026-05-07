import type {
  DocTypeSummary,
  ImportedInput,
  LoopActionResult,
  SessionRecord,
  TaskRecord,
  TimelineEvent,
  WorkspaceFileContent,
  WorkspaceTree,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

export const streamTimelineUrl = (sessionId: string): string =>
  `${API_BASE}/sessions/${sessionId}/timeline/stream`;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const contentTypeHeader: Record<string, string> = init?.body !== undefined
    ? { "Content-Type": "application/json" }
    : {};
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { ...contentTypeHeader, ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    let detail = "";
    try {
      const body = (await response.json()) as { detail?: unknown };
      detail = typeof body.detail === "string" ? `: ${body.detail}` : "";
    } catch {
      detail = "";
    }
    throw new Error(`${response.status} ${response.statusText}${detail}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  listDocTypes: () => request<DocTypeSummary[]>("/doc-types"),
  getDocType: (id: string) => request<DocTypeSummary>(`/doc-types/${id}`),
  listTasks: () => request<TaskRecord[]>("/tasks"),
  createTask: (doc_type_id: string, input: string | { title: string; description: string }) =>
    request<TaskRecord>("/tasks", {
      method: "POST",
      body: JSON.stringify(
        typeof input === "string"
          ? { doc_type_id, brief: input }
          : { doc_type_id, title: input.title, description: input.description },
      ),
    }),
  listTaskSessions: (taskId: string) => request<SessionRecord[]>(`/tasks/${taskId}/sessions`),
  createSession: (taskId: string) =>
    request<SessionRecord>(`/tasks/${taskId}/sessions`, { method: "POST" }),
  getWorkspace: (taskId: string) => request<WorkspaceTree>(`/tasks/${taskId}/workspace`),
  getWorkspaceFile: (taskId: string, path: string) =>
    request<WorkspaceFileContent>(`/tasks/${taskId}/workspace/files?path=${encodeURIComponent(path)}`),
  importTextInput: (taskId: string, name: string, content: string) =>
    request<ImportedInput>(`/tasks/${taskId}/inputs/text`, {
      method: "POST",
      body: JSON.stringify({ name, content }),
    }),
  startLoop: (sessionId: string) =>
    request<LoopActionResult>(`/sessions/${sessionId}/loop/start?background=true`, { method: "POST" }),
  approveOutline: (sessionId: string, outline_markdown: string) =>
    request<LoopActionResult>(`/sessions/${sessionId}/outline/approve?background=true`, {
      method: "POST",
      body: JSON.stringify({ outline_markdown }),
    }),
  reviseSelection: (sessionId: string, selected_text: string, instruction: string) =>
    request<LoopActionResult>(`/sessions/${sessionId}/revision/selection?background=true`, {
      method: "POST",
      body: JSON.stringify({ selected_text, instruction }),
    }),
  runChecklist: (sessionId: string) =>
    request<LoopActionResult>(`/sessions/${sessionId}/checklist/run?background=true`, { method: "POST" }),
  exportMarkdown: (sessionId: string) =>
    request<LoopActionResult>(`/sessions/${sessionId}/artifacts/export-markdown?background=true`, { method: "POST" }),
  sendMessage: (sessionId: string, message: string) =>
    request<{ accepted?: boolean; event_count?: number; status?: string }>(
      `/sessions/${sessionId}/messages?background=true`,
      {
        method: "POST",
        body: JSON.stringify({ message }),
      },
    ),
  getTimeline: (sessionId: string) => request<TimelineEvent[]>(`/sessions/${sessionId}/timeline`),
  getDraft: (taskId: string) => request<{ markdown: string }>(`/tasks/${taskId}/draft`),
  updateDraft: (taskId: string, markdown: string) =>
    request<{ markdown: string }>(`/tasks/${taskId}/draft`, {
      method: "PUT",
      body: JSON.stringify({ markdown }),
    }),
};
