import { ExternalLink } from "lucide-react";
import type { TimelineEvent } from "../../../types";

interface CheckpointCardProps {
  event: TimelineEvent;
  onOpenPath: (path: string) => Promise<void>;
}

export function CheckpointCard({ event, onOpenPath }: CheckpointCardProps) {
  const path = event.paths.find((item) => item.startsWith("versions/")) ?? event.paths[0];

  return (
    <article className="inline-card">
      <header>
        <strong>Checkpoint · {path ?? event.status}</strong>
        {path && (
          <button type="button" onClick={() => void onOpenPath(path)}>
            <ExternalLink size={14} /> Open
          </button>
        )}
      </header>
      <p>{event.summary}</p>
    </article>
  );
}
