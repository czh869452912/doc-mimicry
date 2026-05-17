import type { AcpEvent, TimelineEvent } from "../../types";
import { ApprovalCard } from "../conversation/cards/ApprovalCard";
import { ArtifactCard } from "../conversation/cards/ArtifactCard";
import { CheckpointCard } from "../conversation/cards/CheckpointCard";
import { ChecklistCard } from "../conversation/cards/ChecklistCard";
import { OutlineCard } from "../conversation/cards/OutlineCard";
import { pathsFromAcpEvent, textFromAcpEvent } from "./acpEvents";

interface AcpRenderSlotsProps {
  event: AcpEvent;
  sessionId: string | null;
  taskId: string | null;
  onApproved: () => Promise<void>;
  onOpenPath: (path: string) => Promise<void>;
}

const SLOT_KINDS = [
  "propose_outline",
  "create_checkpoint",
  "run_checklist",
  "export_markdown",
  "export_docx",
  "export_pdf",
  "approval_requested",
];

export function AcpRenderSlot({
  event,
  onApproved,
  onOpenPath,
  sessionId,
  taskId,
}: AcpRenderSlotsProps) {
  const timelineKind = timelineKindForEvent(event);
  const timelineEvent = toTimelineEvent(event, taskId, timelineKind);

  if (timelineKind === "propose_outline") {
    return <OutlineCard event={timelineEvent} sessionId={sessionId} taskId={taskId} onApproved={onApproved} onOpenPath={onOpenPath} />;
  }
  if (timelineKind === "create_checkpoint") {
    return <CheckpointCard event={timelineEvent} onOpenPath={onOpenPath} />;
  }
  if (timelineKind === "run_checklist") {
    return <ChecklistCard event={timelineEvent} onOpenPath={onOpenPath} />;
  }
  if (timelineKind === "export_markdown" || timelineKind === "export_docx" || timelineKind === "export_pdf") {
    return <ArtifactCard event={timelineEvent} onOpenPath={onOpenPath} />;
  }
  if (timelineKind === "approval_requested") {
    return <ApprovalCard event={timelineEvent} />;
  }
  return null;
}

export function hasAcpRenderSlot(event: AcpEvent): boolean {
  return SLOT_KINDS.includes(timelineKindForEvent(event));
}

function timelineKindForEvent(event: AcpEvent): string {
  return typeof event.projection.timeline_kind === "string" ? event.projection.timeline_kind : "";
}

function toTimelineEvent(event: AcpEvent, taskId: string | null, timelineKind: string): TimelineEvent {
  const paths = pathsFromAcpEvent(event);
  return {
    id: typeof event.projection.timeline_id === "string" ? event.projection.timeline_id : event.id,
    session_id: event.session_id,
    task_id: taskId ?? "",
    actor: typeof event.projection.actor === "string" ? event.projection.actor : "agent",
    kind: timelineKind || event.event_type,
    raw_event_id: event.id,
    summary: typeof event.projection.summary === "string" ? event.projection.summary : textFromAcpEvent(event) || event.event_type,
    paths,
    status: typeof event.projection.status === "string" ? event.projection.status : "succeeded",
    created_at: event.created_at,
  };
}
