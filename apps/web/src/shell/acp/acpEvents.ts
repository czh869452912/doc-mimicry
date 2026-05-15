import type { AcpEvent } from "../../types";

export type AcpEventFamily = "message" | "tool" | "file" | "permission" | "status" | "unknown";
export type AcpDisplayStatus = "running" | "succeeded" | "failed" | "cancelled" | "pending";

export interface ClassifiedAcpEvent {
  family: AcpEventFamily;
  role: "user" | "assistant" | "tool" | "system";
  status: AcpDisplayStatus;
  title: string;
  paths: string[];
}

export interface AcpInvalidationHints {
  workspace: boolean;
  draft: boolean;
  sessions: boolean;
  paths: string[];
}

export function classifyAcpEvent(event: AcpEvent): ClassifiedAcpEvent {
  const eventType = event.event_type.toLowerCase();
  const family = familyForEvent(event);
  return {
    family,
    role: roleForEvent(event, family),
    status: statusForEventType(eventType, event.payload.status),
    title: titleForEvent(event, family),
    paths: pathsFromAcpEvent(event),
  };
}

export function mergeAcpEvents(events: AcpEvent[]): AcpEvent[] {
  const byId = new Map<string, AcpEvent>();
  const order: string[] = [];

  for (const event of [...events].sort((a, b) => a.sequence - b.sequence)) {
    const mergeId = mergeIdForEvent(event);
    const existing = byId.get(mergeId);
    if (!existing) {
      const normalized = mergeId === event.id ? event : { ...event, id: mergeId };
      byId.set(mergeId, normalized);
      order.push(mergeId);
      continue;
    }
    byId.set(mergeId, mergeEvent(existing, event, mergeId));
  }

  return order.map((id) => byId.get(id)).filter((event): event is AcpEvent => Boolean(event));
}

export function textFromAcpEvent(event: AcpEvent): string {
  return (
    stringValue(event.payload.prompt)
    ?? stringValue(event.payload.content)
    ?? stringValue(event.payload.delta)
    ?? stringValue(event.payload.message)
    ?? stringValue(event.projection.summary)
    ?? ""
  );
}

export function pathsFromAcpEvent(event: AcpEvent): string[] {
  const payloadPaths = stringArray(event.payload.paths);
  const projectionPaths = stringArray(event.projection.paths);
  const path = stringValue(event.payload.path);
  return uniqueStrings([...payloadPaths, ...(path ? [path] : []), ...projectionPaths]);
}

export function deriveAcpInvalidationHints(events: AcpEvent[]): AcpInvalidationHints {
  const paths = uniqueStrings(events.flatMap(pathsFromAcpEvent));
  const hasStatus = events.some((event) => isSessionStatusEvent(event));
  return {
    workspace: paths.length > 0,
    draft: paths.some((path) => path.startsWith("draft/")),
    sessions: hasStatus || events.some((event) => event.event_type.toLowerCase().includes("error")),
    paths,
  };
}

function isSessionStatusEvent(event: AcpEvent): boolean {
  if (classifyAcpEvent(event).family === "status") return true;
  return stringValue(event.projection.timeline_kind) === "session_status"
    || stringValue(event.projection.actor) === "system";
}

export function findReloadInput(events: AcpEvent[], parentEventId: string | null): string | null {
  const merged = mergeAcpEvents(events);
  const parentIndex = parentEventId
    ? merged.findIndex((event) => event.id === parentEventId)
    : merged.length;
  const endIndex = parentIndex >= 0 ? parentIndex : merged.length;

  for (let index = endIndex - 1; index >= 0; index -= 1) {
    const event = merged[index];
    if (classifyAcpEvent(event).role === "user") {
      const input = textFromAcpEvent(event).trim();
      if (input) return input;
    }
  }
  return null;
}

function familyForEvent(event: AcpEvent): AcpEventFamily {
  const eventType = event.event_type.toLowerCase();
  if (eventType.includes("message") || eventType.includes("prompt") || eventType.includes("session/update")) return "message";
  if (eventType.includes("tool") || eventType.includes("command") || eventType.includes("terminal")) return "tool";
  if (eventType.includes("file")) return "file";
  if (eventType.includes("permission") || eventType.includes("approval")) return "permission";
  if (eventType.includes("session/") || eventType.includes("status") || eventType.includes("cancel") || eventType.includes("error")) return "status";
  return "unknown";
}

function roleForEvent(event: AcpEvent, family: AcpEventFamily): ClassifiedAcpEvent["role"] {
  const role = stringValue(event.payload.role) ?? stringValue(event.projection.actor);
  if (role === "user") return "user";
  if (role === "tool") return "tool";
  if (role === "system") return "system";
  if (event.event_type.toLowerCase().includes("prompt")) return "user";
  if (family === "tool" || family === "file") return "tool";
  if (family === "permission" || family === "status") return "system";
  return "assistant";
}

function titleForEvent(event: AcpEvent, family: AcpEventFamily): string {
  const projected = stringValue(event.projection.summary);
  if (projected) return projected;
  if (family === "message") return roleForEvent(event, family) === "user" ? "You" : "Agent";
  if (family === "tool") return stringValue(event.payload.name) ?? stringValue(event.payload.tool_name) ?? "Tool";
  if (family === "file") return stringValue(event.payload.path) ?? "File activity";
  if (family === "permission") return permissionTitle(event);
  if (family === "status") return "Session status";
  return event.event_type;
}

function statusForEventType(eventType: string, payloadStatus: unknown): AcpDisplayStatus {
  const status = stringValue(payloadStatus);
  if (status === "failed" || status === "cancelled" || status === "pending" || status === "running" || status === "succeeded") return status;
  if (eventType.includes("fail") || eventType.includes("error")) return "failed";
  if (eventType.includes("cancel")) return "cancelled";
  if (eventType.includes("request")) return "pending";
  if (eventType.includes("permission/resolved") || eventType.includes("permission/response")) return "succeeded";
  if (eventType.includes("complete") || eventType.includes("result") || eventType.includes("done")) return "succeeded";
  return "running";
}

function permissionTitle(event: AcpEvent): string {
  const eventType = event.event_type.toLowerCase();
  if (eventType.includes("resolved")) return "Permission resolved";
  if (eventType.includes("response")) return "Permission response";
  return "Permission requested";
}

function mergeIdForEvent(event: AcpEvent): string {
  if (classifyAcpEvent(event).family !== "message") return event.id;
  const messageId = stringValue(event.payload.message_id) ?? stringValue(event.payload.id);
  return messageId ? `acp-message-${messageId}` : event.id;
}

function mergeEvent(existing: AcpEvent, incoming: AcpEvent, mergeId: string): AcpEvent {
  const existingText = textFromAcpEvent(existing);
  const incomingText = textFromAcpEvent(incoming);
  const nextPayload = {
    ...existing.payload,
    ...incoming.payload,
    content: existingText + incomingText,
  };
  return {
    ...incoming,
    id: mergeId,
    payload: nextPayload,
    projection: { ...existing.projection, ...incoming.projection },
  };
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function uniqueStrings(values: string[]): string[] {
  return [...new Set(values.filter((value) => value.length > 0))];
}
