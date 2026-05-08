import type { DocAgentAssistantData } from "./docAgentAssistantMessages";
import { ApprovalCard } from "../conversation/cards/ApprovalCard";
import { ArtifactCard } from "../conversation/cards/ArtifactCard";
import { ChecklistCard } from "../conversation/cards/ChecklistCard";
import { OutlineCard } from "../conversation/cards/OutlineCard";

interface DocAgentMessagePartProps {
  activeSessionId: string | null;
  data: DocAgentAssistantData;
  taskId: string | null;
  onApproved: () => Promise<void>;
  onOpenPath: (path: string) => Promise<void>;
}

export function DocAgentMessagePart({
  activeSessionId,
  data,
  onApproved,
  onOpenPath,
  taskId,
}: DocAgentMessagePartProps) {
  if (data.kind === "event-pill") {
    return (
      <div className="aui-timeline-part aui-timeline-part--event">
        <article className="aui-event-pill-row">
          <span className="event-pill" data-category={data.category}>
            {data.event.kind}
          </span>
          <span>{data.summary}</span>
          {data.meta && <small>{data.meta}</small>}
        </article>
      </div>
    );
  }

  if (data.kind === "outline-card") {
    return (
      <div className="aui-timeline-part aui-timeline-part--card">
        <OutlineCard
          event={data.event}
          sessionId={activeSessionId}
          taskId={taskId}
          onApproved={onApproved}
          onOpenPath={onOpenPath}
        />
      </div>
    );
  }

  if (data.kind === "checklist-card") {
    return (
      <div className="aui-timeline-part aui-timeline-part--card">
        <ChecklistCard event={data.event} onOpenPath={onOpenPath} />
      </div>
    );
  }

  if (data.kind === "artifact-card") {
    return (
      <div className="aui-timeline-part aui-timeline-part--card">
        <ArtifactCard event={data.event} onOpenPath={onOpenPath} />
      </div>
    );
  }

  return (
    <div className="aui-timeline-part aui-timeline-part--card">
      <ApprovalCard event={data.event} />
    </div>
  );
}
