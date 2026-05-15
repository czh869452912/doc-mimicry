import { Copy, RefreshCcw } from "lucide-react";
import type { AcpEvent } from "../../types";
import { classifyAcpEvent, textFromAcpEvent } from "./acpEvents";
import { AcpRenderSlot, hasAcpRenderSlot } from "./AcpRenderSlots";

interface AcpEventRendererProps {
  event: AcpEvent;
  sessionId: string | null;
  taskId: string | null;
  onApproved: () => Promise<void>;
  onCopy: (event: AcpEvent) => Promise<void>;
  onOpenPath: (path: string) => Promise<void>;
  onReloadInput: (eventId: string) => Promise<void>;
}

export function AcpEventRenderer({
  event,
  onApproved,
  onCopy,
  onOpenPath,
  onReloadInput,
  sessionId,
  taskId,
}: AcpEventRendererProps) {
  const classified = classifyAcpEvent(event);
  const text = textFromAcpEvent(event);
  const isAssistantMessage = classified.family === "message" && classified.role === "assistant";
  const alignment = classified.role === "user" ? "user" : "assistant";

  if (hasAcpRenderSlot(event)) {
    return (
      <article className="acp-event acp-event--card" data-family={classified.family}>
        <AcpRenderSlot event={event} sessionId={sessionId} taskId={taskId} onApproved={onApproved} onOpenPath={onOpenPath} />
      </article>
    );
  }

  return (
    <article className={`acp-event acp-event--${alignment}`} data-family={classified.family} data-status={classified.status}>
      <div className="acp-event__body">
        {classified.family === "message" ? (
          <p className="acp-event__text">{text}</p>
        ) : (
          <>
            <header className="acp-event__header">
              <strong>{classified.title}</strong>
              <span>{classified.status}</span>
            </header>
            {text && <p className="acp-event__text">{text}</p>}
            {classified.paths.length > 0 && (
              <button type="button" className="acp-event__path" onClick={() => void onOpenPath(classified.paths[0])}>
                {classified.paths.join(", ")}
              </button>
            )}
            {classified.family === "unknown" && (
              <pre className="acp-event__payload">{JSON.stringify(event.payload, null, 2)}</pre>
            )}
          </>
        )}
      </div>
      <div className="acp-event__actions">
        {text && (
          <button type="button" className="acp-icon-button" aria-label="Copy text" onClick={() => void onCopy(event)}>
            <Copy size={14} />
          </button>
        )}
        {isAssistantMessage && (
          <button type="button" className="acp-icon-button" aria-label="Reload response" onClick={() => void onReloadInput(event.id)}>
            <RefreshCcw size={14} />
          </button>
        )}
      </div>
    </article>
  );
}
