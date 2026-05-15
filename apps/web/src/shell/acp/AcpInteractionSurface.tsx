import { RefreshCcw } from "lucide-react";
import type { ReactNode } from "react";
import type { AcpEvent, MessageAttachment } from "../../types";
import { findReloadInput, mergeAcpEvents, textFromAcpEvent } from "./acpEvents";
import { AcpComposer } from "./AcpComposer";
import { AcpEventRenderer } from "./AcpEventRenderer";

export type AcpPermissionDecision = "allow" | "deny";

export type AcpRenderSlots = (props: {
  event: AcpEvent;
  sessionId: string | null;
  taskId: string | null;
  onApproved: () => Promise<void>;
  onOpenPath: (path: string) => Promise<void>;
}) => ReactNode;

export interface AcpInteractionSurfaceProps {
  sessionId: string | null;
  taskId: string | null;
  events: AcpEvent[];
  emptyMessage: string | null;
  loading: boolean;
  running: boolean;
  error: string | null;
  queuedComposerDraft?: string | null;
  renderSlots?: AcpRenderSlots;
  onApproved: () => Promise<void>;
  onAnswerPermission?: (requestId: string, decision: AcpPermissionDecision) => Promise<void>;
  // Attachments are currently imported by AcpComposer before send; this port keeps
  // third-party ACP UI adapters from depending on that implementation detail.
  onAttachContext?: (attachments: MessageAttachment[]) => Promise<void>;
  onCancel: () => Promise<void>;
  onCopyContent?: (content: { text: string; eventId?: string }) => Promise<void>;
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
  onAnswerPermission,
  onAttachContext,
  onCancel,
  onCopyContent,
  onOpenPath,
  onQueuedComposerDraftHandled,
  onReloadInput,
  onSendMessage,
  queuedComposerDraft,
  renderSlots,
  running,
  sessionId,
  taskId,
}: AcpInteractionSurfaceProps) {
  const mergedEvents = mergeAcpEvents(events);
  const canReloadLastInput = findReloadInput(mergedEvents, null) !== null;

  async function copyEvent(event: AcpEvent) {
    const text = textFromAcpEvent(event);
    if (onCopyContent) {
      await onCopyContent({ text, eventId: event.id });
      return;
    }
    await navigator.clipboard?.writeText(text);
  }

  return (
    <section className="acp-surface">
      <div className="acp-thread">
        <div className="acp-thread-viewport">
          {canReloadLastInput && (
            <div className="acp-surface-actions">
              <button type="button" className="acp-icon-button" aria-label="Reload last user message" onClick={() => void onReloadInput(null)}>
                <RefreshCcw size={14} />
              </button>
            </div>
          )}
          {emptyMessage && mergedEvents.length === 0 && <div className="conversation-empty">{emptyMessage}</div>}
          {mergedEvents.map((event) => (
            <AcpEventRenderer
              key={event.id}
              event={event}
              sessionId={sessionId}
              taskId={taskId}
              renderSlots={renderSlots}
              onApproved={onApproved}
              onAnswerPermission={onAnswerPermission}
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
        onAttachContext={onAttachContext}
        onCancel={onCancel}
        onDraftTextApplied={onQueuedComposerDraftHandled}
        onSend={onSendMessage}
        taskId={taskId}
      />
      {error && <p className="pane-note pane-note--error">{error}</p>}
    </section>
  );
}
