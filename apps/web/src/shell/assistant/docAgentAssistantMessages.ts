import type { ThreadMessage } from "@assistant-ui/react";
import type { TimelineEvent } from "../../types";

export type PillCategory = "thinking" | "grep" | "read" | "edit" | "done";

export type DocAgentAssistantData =
  | { kind: "event-pill"; category: PillCategory; summary: string; meta?: string; event: TimelineEvent }
  | { kind: "outline-card"; event: TimelineEvent }
  | { kind: "checklist-card"; event: TimelineEvent }
  | { kind: "artifact-card"; event: TimelineEvent }
  | { kind: "approval-card"; event: TimelineEvent };

type AssistantDataName =
  | "docagent.event-pill"
  | "docagent.outline-card"
  | "docagent.checklist-card"
  | "docagent.artifact-card"
  | "docagent.approval-card";

export function mapTimelineEventsToAssistantMessages(events: TimelineEvent[]): ThreadMessage[] {
  return events.map(mapTimelineEventToAssistantMessage);
}

function mapTimelineEventToAssistantMessage(event: TimelineEvent): ThreadMessage {
  const createdAt = new Date(0);
  const custom = { timelineEventId: event.id, timelineKind: event.kind };

  if (event.kind === "user_message") {
    return {
      id: event.id,
      role: "user",
      createdAt,
      content: [{ type: "text", text: event.summary }],
      attachments: [],
      metadata: { custom },
    };
  }

  if (event.kind === "agent_message") {
    return {
      id: event.id,
      role: "assistant",
      createdAt,
      content: [{ type: "text", text: event.summary }],
      status: { type: "complete", reason: "stop" },
      metadata: assistantMetadata(custom),
    };
  }

  const dataPart = dataPartForEvent(event);
  return {
    id: event.id,
    role: "assistant",
    createdAt,
    content: [{ type: "data", ...dataPart }],
    status: { type: "complete", reason: "stop" },
    metadata: assistantMetadata(custom),
  };
}

function dataPartForEvent(event: TimelineEvent): { name: AssistantDataName; data: DocAgentAssistantData } {
  if (event.kind === "approval_requested") {
    return { name: "docagent.approval-card", data: { kind: "approval-card", event } };
  }
  if (event.kind === "propose_outline" && event.paths.includes("draft/outline.md")) {
    return { name: "docagent.outline-card", data: { kind: "outline-card", event } };
  }
  if (event.kind === "run_checklist") {
    return { name: "docagent.checklist-card", data: { kind: "checklist-card", event } };
  }
  if (event.kind === "export_markdown" || event.kind === "export_docx" || event.kind === "export_pdf") {
    return { name: "docagent.artifact-card", data: { kind: "artifact-card", event } };
  }

  return {
    name: "docagent.event-pill",
    data: {
      kind: "event-pill",
      category: categoryForKind(event.kind),
      summary: event.summary || event.kind,
      meta: event.paths.length > 0 ? event.paths.join(", ") : event.kind,
      event,
    },
  };
}

function assistantMetadata(custom: Record<string, unknown>) {
  return {
    unstable_state: null,
    unstable_annotations: [],
    unstable_data: [],
    steps: [],
    custom,
  };
}

function categoryForKind(kind: string): PillCategory {
  if (kind === "read_skill" || kind === "convert_input") return "read";
  if (kind === "analyze_examples") return "grep";
  if (
    kind === "build_context" ||
    kind === "extract_style" ||
    kind === "extract_structure" ||
    kind === "generate_outline" ||
    kind === "propose_outline" ||
    kind === "update_draft" ||
    kind === "revise_selection" ||
    kind === "create_checkpoint"
  ) {
    return "edit";
  }
  if (kind === "approve_outline" || kind === "approval_resolved") return "done";
  return "thinking";
}
