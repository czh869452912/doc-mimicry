import { ExternalLink } from "lucide-react";
import type { TimelineEvent } from "../../../types";

interface ChecklistCardProps {
  event: TimelineEvent;
  onOpenPath: (path: string) => Promise<void>;
}

export function ChecklistCard({ event, onOpenPath }: ChecklistCardProps) {
  const path = event.paths.find((item) => item.includes("checklist")) ?? event.paths[0];

  return (
    <article className="inline-card">
      <header>
        <strong>Checklist · {event.status}</strong>
        {path && (
          <button type="button" onClick={() => void onOpenPath(path)}>
            <ExternalLink size={14} /> Open
          </button>
        )}
      </header>
      <p>{event.summary}</p>
      {event.paths.length > 0 && <small>{event.paths.join(", ")}</small>}
    </article>
  );
}
