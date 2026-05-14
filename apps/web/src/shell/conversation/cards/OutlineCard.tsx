import { CheckCircle2, ExternalLink } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../../../api";
import type { TimelineEvent } from "../../../types";

interface OutlineCardProps {
  event: TimelineEvent;
  sessionId: string | null;
  taskId: string | null;
  onApproved: () => Promise<void>;
  onOpenPath: (path: string) => Promise<void>;
}

export function OutlineCard({ event, onApproved, onOpenPath, sessionId, taskId }: OutlineCardProps) {
  const [outline, setOutline] = useState(event.summary);
  const dirtyRef = useRef(false);
  const outlinePath = event.paths.find((path) => path.endsWith("outline.md")) ?? "draft/outline.md";

  useEffect(() => {
    dirtyRef.current = false;
    setOutline(event.summary);
    if (!taskId) return;
    let cancelled = false;

    api
      .getWorkspaceFile(taskId, outlinePath)
      .then((file) => {
        if (!cancelled && !dirtyRef.current) setOutline(file.content);
      })
      .catch(() => {
        if (!cancelled && !dirtyRef.current) setOutline(event.summary);
      });

    return () => {
      cancelled = true;
    };
  }, [event.id, outlinePath, taskId]);

  async function approve() {
    if (!sessionId) return;
    await api.approveOutline(sessionId, outline);
    await onApproved();
  }

  return (
    <article className="inline-card">
      <header>
        <strong>Outline · waiting for review</strong>
        <button type="button" onClick={() => void onOpenPath(outlinePath)}>
          <ExternalLink size={14} /> Open
        </button>
      </header>
      <textarea
        value={outline}
        onChange={(event) => {
          dirtyRef.current = true;
          setOutline(event.target.value);
        }}
      />
      <footer>
        <button className="primary-button" type="button" disabled={!sessionId} onClick={() => void approve()}>
          <CheckCircle2 size={14} /> Approve
        </button>
      </footer>
    </article>
  );
}
