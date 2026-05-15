export interface AcpUiEmbedContext {
  acpUiUrl?: string | null;
  apiBase?: string | null;
  sessionId: string | null;
  taskId: string | null;
}

export function configuredAcpUiUrl(): string | null {
  const value = import.meta.env.VITE_ACP_UI_URL;
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : null;
}

export function buildAcpUiEmbedUrl({
  acpUiUrl,
  apiBase,
  sessionId,
  taskId,
}: AcpUiEmbedContext): string | null {
  const base = acpUiUrl?.trim();
  if (!base) return null;
  const url = new URL(base, window.location.origin);
  if (sessionId) url.searchParams.set("docagentSessionId", sessionId);
  if (taskId) url.searchParams.set("docagentTaskId", taskId);
  if (apiBase) url.searchParams.set("docagentApiBase", apiBase);
  if (sessionId && apiBase) {
    url.searchParams.set("docagentAcpWsUrl", acpWsUrl(apiBase, sessionId));
  }
  return url.toString();
}

function acpWsUrl(apiBase: string, sessionId: string): string {
  const url = new URL(apiBase, window.location.origin);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = `/sessions/${encodeURIComponent(sessionId)}/acp/ws`;
  url.search = "";
  url.hash = "";
  return url.toString();
}
