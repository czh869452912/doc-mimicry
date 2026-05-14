import type { AcpEvent, TimelineEvent } from "../../types";
import { mergeTimelineEvents } from "./docagentRuntime";

type TimelineActor = TimelineEvent["actor"];

export function projectAcpEventsToTimelineEvents(events: AcpEvent[], taskId: string | null | undefined): TimelineEvent[] {
  return events.reduce<TimelineEvent[]>(
    (projected, event) => mergeProjectedAcpEvent(projected, event, taskId),
    [],
  );
}

export function mergeProjectedAcpEvent(
  existing: TimelineEvent[],
  event: AcpEvent,
  taskId: string | null | undefined,
): TimelineEvent[] {
  const projected = projectAcpEvent(event, taskId);
  const previous = existing.find((item) => item.id === projected.id);
  if (previous && isMessageEvent(event)) {
    const summary = projected.status === "running"
      ? `${previous.summary}${projected.summary}`
      : projected.summary || previous.summary;
    return mergeTimelineEvents(existing, [
      {
        ...projected,
        summary,
      },
    ]);
  }
  return mergeTimelineEvents(existing, [projected]);
}

function projectAcpEvent(event: AcpEvent, taskId: string | null | undefined): TimelineEvent {
  const projectionKind = stringValue(event.projection.timeline_kind);
  if (projectionKind) return projectedDocAgentEvent(event, taskId, projectionKind);
  if (isMessageEvent(event)) return projectedMessageEvent(event, taskId);
  if (isToolEvent(event)) return projectedToolEvent(event, taskId);
  if (isFileEvent(event)) return projectedFileEvent(event, taskId);
  if (isCommandEvent(event)) return projectedCommandEvent(event, taskId);
  if (isPlanEvent(event)) return projectedPlanEvent(event, taskId);
  if (isPermissionEvent(event)) return projectedPermissionEvent(event, taskId);
  if (isErrorEvent(event)) return projectedErrorEvent(event, taskId);
  return baseTimelineEvent(event, taskId, {
    actor: "system",
    kind: "agent_tool_call",
    status: "succeeded",
    summary: event.event_type,
  });
}

function projectedDocAgentEvent(event: AcpEvent, taskId: string | null | undefined, kind: string): TimelineEvent {
  return baseTimelineEvent(event, taskId, {
    id: stringValue(event.projection.timeline_id) ?? `acp-projection-${event.sequence}`,
    actor: (stringValue(event.projection.actor) as TimelineActor | null) ?? "agent",
    kind,
    paths: stringArray(event.projection.paths),
    status: stringValue(event.projection.status) ?? "succeeded",
    summary: stringValue(event.projection.summary) ?? kind,
  });
}

function projectedMessageEvent(event: AcpEvent, taskId: string | null | undefined): TimelineEvent {
  const role = stringValue(event.payload.role) ?? stringValue(event.projection.actor) ?? "assistant";
  const messageId = stringValue(event.payload.message_id) ?? stringValue(event.payload.id) ?? String(event.sequence);
  const summary = stringValue(event.payload.content) ?? stringValue(event.payload.delta) ?? "";
  const isUser = role === "user";
  const isCompleted = event.event_type.includes("completed") || event.event_type.includes("complete");
  return baseTimelineEvent(event, taskId, {
    id: `acp-message-${messageId}`,
    actor: isUser ? "user" : "agent",
    kind: isUser ? "user_message" : "agent_message",
    status: isCompleted ? "succeeded" : "running",
    summary,
  });
}

function projectedToolEvent(event: AcpEvent, taskId: string | null | undefined): TimelineEvent {
  const toolId = stringValue(event.payload.id) ?? stringValue(event.payload.tool_call_id) ?? String(event.sequence);
  const toolName = stringValue(event.payload.name) ?? stringValue(event.payload.tool_name) ?? "tool";
  const status = stringValue(event.payload.status) ?? statusFromEventType(event.event_type);
  return baseTimelineEvent(event, taskId, {
    id: `acp-tool-${toolId}`,
    actor: "tool",
    kind: "agent_tool_call",
    paths: stringArray(event.payload.paths),
    status,
    summary: `${toolName} ${status}`,
  });
}

function projectedFileEvent(event: AcpEvent, taskId: string | null | undefined): TimelineEvent {
  const paths = stringArray(event.payload.paths);
  const path = stringValue(event.payload.path);
  const allPaths = paths.length > 0 ? paths : path ? [path] : [];
  return baseTimelineEvent(event, taskId, {
    actor: "tool",
    kind: "update_draft",
    paths: allPaths,
    status: stringValue(event.payload.status) ?? statusFromEventType(event.event_type),
    summary: stringValue(event.payload.summary) ?? `File operation${path ? `: ${path}` : ""}`,
  });
}

function projectedCommandEvent(event: AcpEvent, taskId: string | null | undefined): TimelineEvent {
  const command = stringValue(event.payload.command) ?? stringValue(event.payload.name) ?? "command";
  return baseTimelineEvent(event, taskId, {
    actor: "tool",
    kind: "agent_tool_call",
    status: stringValue(event.payload.status) ?? statusFromEventType(event.event_type),
    summary: command,
  });
}

function projectedPlanEvent(event: AcpEvent, taskId: string | null | undefined): TimelineEvent {
  return baseTimelineEvent(event, taskId, {
    actor: "agent",
    kind: "agent_tool_call",
    status: stringValue(event.payload.status) ?? "running",
    summary: stringValue(event.payload.summary) ?? "Plan updated",
  });
}

function projectedPermissionEvent(event: AcpEvent, taskId: string | null | undefined): TimelineEvent {
  return baseTimelineEvent(event, taskId, {
    actor: "system",
    kind: "approval_requested",
    status: "pending",
    summary: stringValue(event.payload.summary) ?? stringValue(event.payload.reason) ?? "Permission requested",
  });
}

function projectedErrorEvent(event: AcpEvent, taskId: string | null | undefined): TimelineEvent {
  return baseTimelineEvent(event, taskId, {
    actor: "system",
    kind: "error",
    status: "failed",
    summary: stringValue(event.payload.message) ?? stringValue(event.payload.error) ?? "Runtime error",
  });
}

function baseTimelineEvent(
  event: AcpEvent,
  taskId: string | null | undefined,
  overrides: Partial<TimelineEvent>,
): TimelineEvent {
  const nextSummary = String(overrides.summary ?? "");
  return {
    id: overrides.id ?? `acp-${event.sequence}`,
    session_id: event.session_id,
    task_id: taskId ?? "",
    actor: overrides.actor ?? "agent",
    kind: overrides.kind ?? event.event_type,
    raw_event_id: event.id,
    summary: nextSummary,
    paths: overrides.paths ?? [],
    status: overrides.status ?? "succeeded",
    created_at: event.created_at,
    raw_acp_event: event,
  };
}

function isMessageEvent(event: AcpEvent): boolean {
  return event.event_type.includes("message") || event.event_type.includes("session/update");
}

function isToolEvent(event: AcpEvent): boolean {
  return event.event_type.includes("tool");
}

function isFileEvent(event: AcpEvent): boolean {
  return event.event_type.includes("file");
}

function isCommandEvent(event: AcpEvent): boolean {
  return event.event_type.includes("command") || event.event_type.includes("terminal");
}

function isPlanEvent(event: AcpEvent): boolean {
  return event.event_type.includes("plan");
}

function isPermissionEvent(event: AcpEvent): boolean {
  return event.event_type.includes("permission") || event.event_type.includes("approval");
}

function isErrorEvent(event: AcpEvent): boolean {
  return event.event_type.includes("error") || event.event_type.includes("cancel");
}

function statusFromEventType(eventType: string): string {
  if (eventType.includes("error") || eventType.includes("failed")) return "failed";
  if (eventType.includes("cancel")) return "cancelled";
  if (eventType.includes("done") || eventType.includes("result") || eventType.includes("complete")) return "succeeded";
  return "running";
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}
