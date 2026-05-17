import type {
  DocTypeSummary,
  ImportedInput,
  LoopActionResult,
  AcpEvent,
  MessageAttachment,
  SessionRecord,
  SkillCreatorRunResult,
  SkillCreatorSession,
  SkillPackArtifact,
  SkillPackResource,
  SkillPackSummary,
  SkillPackValidation,
  SkillPackVersion,
  TaskRecord,
  WorkspaceFileContent,
  WorkspaceTree,
} from "./types";

export const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

export const streamAcpEventsUrl = (sessionId: string): string =>
  `${API_BASE}/sessions/${sessionId}/events/stream`;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = typeof FormData !== "undefined" && init?.body instanceof FormData;
  const contentTypeHeader: Record<string, string> = init?.body !== undefined && !isFormData
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

function upload<T>(path: string, body: FormData): Promise<T> {
  return request<T>(path, { method: "POST", body });
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
  importFileInput: (taskId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return upload<ImportedInput>(`/tasks/${taskId}/inputs/files`, formData);
  },
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
  sendMessage: (sessionId: string, message: string, attachments: MessageAttachment[] = []) =>
    request<LoopActionResult>(
      `/sessions/${sessionId}/messages?background=true`,
      {
        method: "POST",
        body: JSON.stringify({ message, attachments }),
      },
    ),
  cancelSession: (sessionId: string) =>
    request<LoopActionResult>(`/sessions/${sessionId}/cancel`, { method: "POST" }),
  answerPermission: (sessionId: string, requestId: string, decision: "allow" | "deny") =>
    request<LoopActionResult>(
      `/sessions/${sessionId}/permissions/${encodeURIComponent(requestId)}/answer`,
      {
        method: "POST",
        body: JSON.stringify({ decision }),
      },
    ),
  getAcpEvents: (sessionId: string) => request<AcpEvent[]>(`/sessions/${sessionId}/events`),
  getDraft: (taskId: string) => request<{ markdown: string }>(`/tasks/${taskId}/draft`),
  updateDraft: (taskId: string, markdown: string) =>
    request<{ markdown: string }>(`/tasks/${taskId}/draft`, {
      method: "PUT",
      body: JSON.stringify({ markdown }),
    }),
  listSkillPacks: () => request<SkillPackSummary[]>("/skill-packs"),
  createSkillPack: (id: string, title: string, description: string) =>
    request<SkillPackSummary>("/skill-packs", {
      method: "POST",
      body: JSON.stringify({ id, title, description }),
    }),
  addSkillPackTextResource: (
    packId: string,
    group: SkillPackResource["group"],
    name: string,
    content: string,
  ) =>
    request<SkillPackResource>(`/skill-packs/${packId}/resources/text`, {
      method: "POST",
      body: JSON.stringify({ group, name, content }),
    }),
  addSkillPackFileResource: (packId: string, group: SkillPackResource["group"], file: File) => {
    const formData = new FormData();
    formData.append("group", group);
    formData.append("file", file);
    return upload<SkillPackResource>(`/skill-packs/${packId}/resources/files`, formData);
  },
  updateSkillPackArtifact: (packId: string, path: string, content: string, summary: string) =>
    request<SkillPackArtifact>(`/skill-packs/${packId}/artifacts`, {
      method: "PUT",
      body: JSON.stringify({ path, content, summary }),
    }),
  getSkillPackArtifact: (packId: string, path: string) =>
    request<SkillPackArtifact>(`/skill-packs/${packId}/artifacts?path=${encodeURIComponent(path)}`),
  createSkillCreatorSession: (packId: string, message: string) =>
    request<SkillCreatorSession>(`/skill-packs/${packId}/skill-creator/sessions`, {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
  generateSkillPack: (packId: string, sessionId: string, message: string) =>
    request<SkillCreatorRunResult>(`/skill-packs/${packId}/skill-creator/sessions/${sessionId}/generate`, {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
  sendSkillCreatorMessage: (packId: string, sessionId: string, message: string) =>
    request<SkillCreatorRunResult>(`/skill-packs/${packId}/skill-creator/sessions/${sessionId}/messages`, {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
  validateSkillPack: (packId: string) =>
    request<SkillPackValidation>(`/skill-packs/${packId}/validate`, { method: "POST" }),
  publishSkillPack: (packId: string, publish_note: string, acknowledged_warnings: string[] = []) =>
    request<SkillPackVersion>(`/skill-packs/${packId}/publish`, {
      method: "POST",
      body: JSON.stringify({ publish_note, acknowledged_warnings }),
    }),
};
