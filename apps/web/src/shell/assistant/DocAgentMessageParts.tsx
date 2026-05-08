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
      <article className="aui-event-pill-row">
        <span className="event-pill" data-category={data.category}>
          {data.event.kind}
        </span>
        <span>{data.summary}</span>
        {data.meta && <small>{data.meta}</small>}
      </article>
    );
  }

  if (data.kind === "outline-card") {
    return (
      <OutlineCard
        event={data.event}
        sessionId={activeSessionId}
        taskId={taskId}
        onApproved={onApproved}
        onOpenPath={onOpenPath}
      />
    );
  }

  if (data.kind === "checklist-card") {
    return <ChecklistCard event={data.event} onOpenPath={onOpenPath} />;
  }

  if (data.kind === "artifact-card") {
    return <ArtifactCard event={data.event} onOpenPath={onOpenPath} />;
  }

  return <ApprovalCard event={data.event} />;
}
