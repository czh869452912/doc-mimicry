import { ExternalLink } from "lucide-react";
import type { TimelineEvent } from "../../../types";

interface ArtifactCardProps {
  event: TimelineEvent;
  onOpenPath: (path: string) => Promise<void>;
}

export function ArtifactCard({ event, onOpenPath }: ArtifactCardProps) {
  const path = event.paths.find((item) => item.startsWith("artifacts/")) ?? event.paths[0];

  return (
    <article className="inline-card">
      <header>
        <strong>Artifact · {path ?? event.kind}</strong>
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
