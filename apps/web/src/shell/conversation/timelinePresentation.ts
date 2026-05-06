import type { TimelineEvent } from "../../types";

export type PillCategory = "thinking" | "grep" | "read" | "edit" | "done";

export type Presentation =
  | { kind: "message"; role: "user" | "agent"; body: string; event: TimelineEvent }
  | { kind: "pill"; category: PillCategory; summary: string; meta?: string; event: TimelineEvent }
  | { kind: "card"; cardType: "outline" | "checklist" | "approval" | "artifact"; payload: TimelineEvent };

export const KNOWN_TIMELINE_KINDS = [
  "user_message",
  "agent_message",
  "read_skill",
  "analyze_examples",
  "convert_input",
  "build_context",
  "extract_style",
  "extract_structure",
  "generate_outline",
  "propose_outline",
  "approve_outline",
  "update_draft",
  "revise_selection",
  "create_checkpoint",
  "run_checklist",
  "export_markdown",
  "export_docx",
  "export_pdf",
  "approval_requested",
  "approval_resolved",
  "error",
] as const;

export function timelinePresentation(event: TimelineEvent): Presentation {
  if (event.kind === "user_message") return { kind: "message", role: "user", body: event.summary, event };
  if (event.kind === "agent_message") return { kind: "message", role: "agent", body: event.summary, event };
  if (event.kind === "approval_requested") return { kind: "card", cardType: "approval", payload: event };
  if (event.kind === "propose_outline" && event.paths.includes("draft/outline.md")) {
    return { kind: "card", cardType: "outline", payload: event };
  }
  if (event.kind === "run_checklist") return { kind: "card", cardType: "checklist", payload: event };
  if (event.kind === "export_markdown" || event.kind === "export_docx" || event.kind === "export_pdf") {
    return { kind: "card", cardType: "artifact", payload: event };
  }

  return {
    kind: "pill",
    category: categoryForKind(event.kind),
    summary: event.summary || event.kind,
    meta: event.paths.length > 0 ? event.paths.join(", ") : event.kind,
    event,
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
  if (kind === "error") return "thinking";
  return "thinking";
}
