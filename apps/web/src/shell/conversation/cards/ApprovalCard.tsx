import type { TimelineEvent } from "../../../types";

interface ApprovalCardProps {
  event: TimelineEvent;
}

export function ApprovalCard({ event }: ApprovalCardProps) {
  return (
    <article className="inline-card inline-card--approval">
      <header>
        <strong>Approval requested</strong>
      </header>
      <p>{event.summary}</p>
      {event.paths.length > 0 && <small>{event.paths.join(", ")}</small>}
    </article>
  );
}
