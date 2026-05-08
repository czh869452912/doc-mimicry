import type { ThreadMessage } from "@assistant-ui/react";
import type { TimelineEvent } from "../../types";

export type ToolCallCategory = "read" | "search" | "write" | "review" | "export" | "system";
export type ToolCallDisplayStatus = "running" | "succeeded" | "failed" | "cancelled";

export interface DocAgentToolCallData {
  kind: "tool-call";
  category: ToolCallCategory;
  event: TimelineEvent;
  pathSummary?: string;
  paths: string[];
  status: ToolCallDisplayStatus;
  summary: string;
  title: string;
  toolName: string;
}

export type DocAgentAssistantData =
  | DocAgentToolCallData
  | { kind: "outline-card"; event: TimelineEvent }
  | { kind: "checklist-card"; event: TimelineEvent }
  | { kind: "artifact-card"; event: TimelineEvent }
  | { kind: "approval-card"; event: TimelineEvent };

type AssistantDataName =
  | "docagent.tool-call"
  | "docagent.outline-card"
  | "docagent.checklist-card"
  | "docagent.artifact-card"
  | "docagent.approval-card";

export function mapTimelineEventsToAssistantMessages(events: TimelineEvent[]): ThreadMessage[] {
  return events.map(mapTimelineEventToAssistantMessage);
}

function mapTimelineEventToAssistantMessage(event: TimelineEvent): ThreadMessage {
  const createdAt = event.created_at ? new Date(event.created_at) : new Date(0);
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
      status: threadStatusForEvent(event.status),
      metadata: assistantMetadata(custom),
    };
  }

  const dataPart = dataPartForEvent(event);
  return {
    id: event.id,
    role: "assistant",
    createdAt,
    content: [{ type: "data", ...dataPart }],
    status: threadStatusForEvent(event.status),
    metadata: assistantMetadata(custom),
  };
}

function dataPartForEvent(event: TimelineEvent): { name: AssistantDataName; data: DocAgentAssistantData } {
  if (event.kind === "approval_requested") {
    return { name: "docagent.approval-card", data: { kind: "approval-card", event } };
  }
  if (event.kind === "propose_outline") {
    return { name: "docagent.outline-card", data: { kind: "outline-card", event } };
  }
  if (event.kind === "run_checklist") {
    return { name: "docagent.checklist-card", data: { kind: "checklist-card", event } };
  }
  if (event.kind === "export_markdown" || event.kind === "export_docx" || event.kind === "export_pdf") {
    return { name: "docagent.artifact-card", data: { kind: "artifact-card", event } };
  }

  return {
    name: "docagent.tool-call",
    data: toolCallDataForEvent(event),
  };
}

function toolCallDataForEvent(event: TimelineEvent): DocAgentToolCallData {
  return {
    kind: "tool-call",
    category: categoryForKind(event.kind),
    event,
    paths: event.paths,
    pathSummary: event.paths.length > 0 ? event.paths.join(", ") : undefined,
    status: statusForEvent(event.status),
    summary: event.summary || event.kind,
    title: titleForKind(event.kind),
    toolName: event.kind,
  };
}

function titleForKind(kind: string): string {
  const titles: Record<string, string> = {
    read_skill: "Read document skill",
    analyze_examples: "Analyze examples",
    build_context: "Build context",
    extract_style: "Extract style notes",
    extract_structure: "Extract structure notes",
    generate_outline: "Generate outline",
    update_draft: "Update draft",
    revise_selection: "Revise selection",
    create_checkpoint: "Create checkpoint",
    run_checklist: "Run checklist",
    export_markdown: "Export Markdown",
    export_docx: "Export DOCX",
    export_pdf: "Export PDF",
    convert_input: "Convert input",
  };
  return titles[kind] ?? kind.replaceAll("_", " ");
}

function statusForEvent(status: string): ToolCallDisplayStatus {
  if (status === "failed") return "failed";
  if (status === "cancelled") return "cancelled";
  if (status === "running" || status === "pending") return "running";
  return "succeeded";
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

function threadStatusForEvent(status: string): NonNullable<ThreadMessage["status"]> {
  if (status === "running" || status === "pending") return { type: "running" };
  if (status === "failed") return { type: "incomplete", reason: "error" };
  if (status === "cancelled") return { type: "incomplete", reason: "cancelled" };
  return { type: "complete", reason: "stop" };
}

function categoryForKind(kind: string): ToolCallCategory {
  if (kind === "read_skill" || kind === "convert_input") return "read";
  if (kind === "analyze_examples") return "search";
  if (kind === "run_checklist") return "review";
  if (kind === "export_markdown" || kind === "export_docx" || kind === "export_pdf") return "export";
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
    return "write";
  }
  return "system";
}
