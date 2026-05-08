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
  if (data.kind === "tool-call") {
    return (
      <div className="aui-timeline-part aui-timeline-part--tool">
        <article className="aui-tool-call" data-category={data.category} data-status={data.status}>
          <header className="aui-tool-call__header">
            <span className="aui-tool-call__name">{data.title}</span>
            <span className="aui-tool-call__status">{data.status}</span>
          </header>
          <p className="aui-tool-call__summary">{data.summary}</p>
          {data.pathSummary && <small className="aui-tool-call__paths">{data.pathSummary}</small>}
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
