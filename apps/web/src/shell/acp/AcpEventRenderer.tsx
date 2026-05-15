import { Check, Copy, RefreshCcw, X } from "lucide-react";
import type { ReactNode } from "react";
import type { AcpEvent } from "../../types";
import { classifyAcpEvent, textFromAcpEvent } from "./acpEvents";
import { AcpRenderSlot, hasAcpRenderSlot } from "./AcpRenderSlots";
import type { AcpPermissionDecision, AcpRenderSlots } from "./AcpInteractionSurface";

interface AcpEventRendererProps {
  event: AcpEvent;
  sessionId: string | null;
  taskId: string | null;
  renderSlots?: AcpRenderSlots;
  onApproved: () => Promise<void>;
  onAnswerPermission?: (requestId: string, decision: AcpPermissionDecision) => Promise<void>;
  onCopy: (event: AcpEvent) => Promise<void>;
  onOpenPath: (path: string) => Promise<void>;
  onReloadInput: (eventId: string | null) => Promise<void>;
}

export function AcpEventRenderer({
  event,
  onApproved,
  onAnswerPermission,
  onCopy,
  onOpenPath,
  onReloadInput,
  renderSlots,
  sessionId,
  taskId,
}: AcpEventRendererProps) {
  const classified = classifyAcpEvent(event);
  const text = textFromAcpEvent(event);
  const isAssistantMessage = classified.family === "message" && classified.role === "assistant";
  const permissionRequestId =
    classified.family === "permission" && isPermissionRequestEvent(event) ? requestIdFromPermissionEvent(event) : null;
  const alignment = classified.role === "user" ? "user" : "assistant";

  if (hasAcpRenderSlot(event)) {
    return (
      <article className="acp-event acp-event--card" data-family={classified.family}>
        {renderSlot(renderSlots, { event, sessionId, taskId, onApproved, onOpenPath })}
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
            {permissionRequestId && onAnswerPermission && (
              <div className="acp-permission-actions">
                <button
                  type="button"
                  className="acp-decision-button acp-decision-button--allow"
                  aria-label="Allow permission request"
                  onClick={() => void onAnswerPermission(permissionRequestId, "allow")}
                >
                  <Check size={13} />
                  Allow
                </button>
                <button
                  type="button"
                  className="acp-decision-button"
                  aria-label="Deny permission request"
                  onClick={() => void onAnswerPermission(permissionRequestId, "deny")}
                >
                  <X size={13} />
                  Deny
                </button>
              </div>
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

function renderSlot(renderSlots: AcpRenderSlots | undefined, props: Parameters<AcpRenderSlots>[0]): ReactNode {
  return renderSlots?.(props) ?? <AcpRenderSlot {...props} />;
}

function requestIdFromPermissionEvent(event: AcpEvent): string | null {
  return stringValue(event.payload.request_id)
    ?? stringValue(event.payload.permission_id)
    ?? stringValue(event.payload.id)
    ?? stringValue(event.projection.request_id)
    ?? event.id;
}

function isPermissionRequestEvent(event: AcpEvent): boolean {
  return event.event_type.toLowerCase().includes("/request");
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}
