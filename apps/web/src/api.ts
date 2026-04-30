import type { DocTypeSummary, SessionRecord, TaskRecord, TimelineEvent } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  listDocTypes: () => request<DocTypeSummary[]>("/doc-types"),
  getDocType: (id: string) => request<DocTypeSummary>(`/doc-types/${id}`),
  createTask: (doc_type_id: string, brief: string) =>
    request<TaskRecord>("/tasks", {
      method: "POST",
      body: JSON.stringify({ doc_type_id, brief }),
    }),
  createSession: (taskId: string) =>
    request<SessionRecord>(`/tasks/${taskId}/sessions`, { method: "POST" }),
  sendMessage: (sessionId: string, message: string) =>
    request<{ event_count: number }>(`/sessions/${sessionId}/messages`, {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
  getTimeline: (sessionId: string) => request<TimelineEvent[]>(`/sessions/${sessionId}/timeline`),
  getDraft: (taskId: string) => request<{ markdown: string }>(`/tasks/${taskId}/draft`),
  updateDraft: (taskId: string, markdown: string) =>
    request<{ markdown: string }>(`/tasks/${taskId}/draft`, {
      method: "PUT",
      body: JSON.stringify({ markdown }),
    }),
};
