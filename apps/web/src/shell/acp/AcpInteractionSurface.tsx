import type { AcpEvent, MessageAttachment } from "../../types";
import { mergeAcpEvents, textFromAcpEvent } from "./acpEvents";
import { AcpComposer } from "./AcpComposer";
import { AcpEventRenderer } from "./AcpEventRenderer";

export interface AcpInteractionSurfaceProps {
  sessionId: string | null;
  taskId: string | null;
  events: AcpEvent[];
  emptyMessage: string | null;
  loading: boolean;
  running: boolean;
  error: string | null;
  queuedComposerDraft?: string | null;
  onApproved: () => Promise<void>;
  onCancel: () => Promise<void>;
  onOpenPath: (path: string) => Promise<void>;
  onQueuedComposerDraftHandled?: () => void;
  onReloadInput: (eventId: string | null) => Promise<void>;
  onSendMessage: (input: string, attachments?: MessageAttachment[]) => Promise<void>;
}

export function AcpInteractionSurface({
  emptyMessage,
  error,
  events,
  loading,
  onApproved,
  onCancel,
  onOpenPath,
  onQueuedComposerDraftHandled,
  onReloadInput,
  onSendMessage,
  queuedComposerDraft,
  running,
  sessionId,
  taskId,
}: AcpInteractionSurfaceProps) {
  const mergedEvents = mergeAcpEvents(events);

  async function copyEvent(event: AcpEvent) {
    await navigator.clipboard?.writeText(textFromAcpEvent(event));
  }

  return (
    <section className="acp-surface">
      <div className="acp-thread">
        <div className="acp-thread-viewport">
          {emptyMessage && mergedEvents.length === 0 && <div className="conversation-empty">{emptyMessage}</div>}
          {mergedEvents.map((event) => (
            <AcpEventRenderer
              key={event.id}
              event={event}
              sessionId={sessionId}
              taskId={taskId}
              onApproved={onApproved}
              onCopy={copyEvent}
              onOpenPath={onOpenPath}
              onReloadInput={onReloadInput}
            />
          ))}
          {(loading || running) && (
            <div className="acp-thread-status" role="status">
              {running ? "Agent is working..." : "Refreshing events..."}
            </div>
          )}
        </div>
      </div>
      <AcpComposer
        disabled={!taskId}
        draftText={queuedComposerDraft}
        isRunning={running}
        onCancel={onCancel}
        onDraftTextApplied={onQueuedComposerDraftHandled}
        onSend={onSendMessage}
        taskId={taskId}
      />
      {error && <p className="pane-note pane-note--error">{error}</p>}
    </section>
  );
}
