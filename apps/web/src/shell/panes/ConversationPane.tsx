import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../api";
import type { AcpEvent, MessageAttachment, SessionRecord, TaskRecord } from "../../types";
import { AcpInteractionSurface } from "../acp/AcpInteractionSurface";
import { findReloadInput } from "../acp/acpEvents";
import { SLASH_COMMANDS, executeSlashCommand } from "../conversation/slashCommands";

interface ConversationPaneProps {
  activeSession: SessionRecord | null;
  activeTask: TaskRecord | null;
  createSession: () => Promise<SessionRecord | null>;
  ensureSession: () => Promise<SessionRecord | null>;
  events: AcpEvent[];
  error: string | null;
  loading: boolean;
  onOpenPath: (path: string) => Promise<void>;
  onQueuedComposerDraftHandled?: () => void;
  onQueuedCommandHandled?: () => void;
  queuedComposerDraft?: string | null;
  queuedCommand?: string | null;
  refreshTimeline: () => Promise<unknown>;
  refreshWorkspace: () => Promise<unknown>;
  refreshSessions?: () => Promise<unknown>;
}

export function ConversationPane({
  activeSession,
  activeTask,
  createSession,
  ensureSession,
  events,
  error,
  loading,
  onQueuedComposerDraftHandled,
  onQueuedCommandHandled,
  onOpenPath,
  queuedComposerDraft,
  queuedCommand,
  refreshTimeline,
  refreshWorkspace,
  refreshSessions,
}: ConversationPaneProps) {
  const [status, setStatus] = useState("");
  const [showHelp, setShowHelp] = useState(false);
  const eventsRef = useRef(events);
  const cancellationInFlightRef = useRef(false);
  const isRunning = Boolean(activeSession?.status?.startsWith("running"));

  useEffect(() => {
    eventsRef.current = events;
  }, [events]);

  const cancelActiveSession = useCallback(async () => {
    if (!activeSession || cancellationInFlightRef.current) return;
    cancellationInFlightRef.current = true;
    try {
      await api.cancelSession(activeSession.id);
      await refreshTimeline();
      await refreshSessions?.();
      setStatus("Cancelled.");
    } catch (caught) {
      setStatus(caught instanceof Error ? caught.message : "Cancel failed.");
    } finally {
      cancellationInFlightRef.current = false;
    }
  }, [activeSession, refreshTimeline, refreshSessions]);

  const submitOrCancel = useCallback(
    async (rawInput: string, attachments: MessageAttachment[] = []) => {
      const input = rawInput.trimEnd();
      if (isRunning && activeSession) {
        if (input) {
          setStatus("Agent is working.");
          return;
        }
        await cancelActiveSession();
        return;
      }

      if (!input) return;

      try {
        const commandResult = await executeSlashCommand(input, {
          activeSession,
          activeTask,
          createSession,
          ensureSession,
          openArtifact: onOpenPath,
          openHelp: () => setShowHelp(true),
          refreshSessions,
          refreshTimeline,
          refreshWorkspace,
        });
        if (commandResult.handled) {
          setStatus(commandResult.message ?? "");
          return;
        }
        if (activeSession && ["completed", "cancelled"].includes(activeSession.status)) {
          setStatus(idleSubmitHint(activeSession.status));
          return;
        }
        const session = await ensureSession();
        if (!session) {
          setStatus("Create a workspace first.");
          return;
        }
        await api.sendMessage(session.id, input, attachments);
        await refreshTimeline();
        await refreshWorkspace();
        await refreshSessions?.();
        setStatus("");
      } catch (caught) {
        setStatus(caught instanceof Error ? caught.message : "Conversation action failed.");
      }
    },
    [
      isRunning,
      activeSession,
      cancelActiveSession,
      activeTask,
      createSession,
      ensureSession,
      onOpenPath,
      refreshTimeline,
      refreshWorkspace,
      refreshSessions,
    ],
  );

  const reloadInput = useCallback(
    async (parentEventId: string | null) => {
      const input = findReloadInput(eventsRef.current, parentEventId);
      if (!input) {
        setStatus("No previous user message to reload.");
        return;
      }
      await submitOrCancel(input);
    },
    [submitOrCancel],
  );

  const composerDisabled = !activeTask;
  const composerHint = composerHintFor(activeSession);

  const queuedCommandHandlingRef = useRef(false);
  useEffect(() => {
    if (!queuedCommand || queuedCommandHandlingRef.current) return;
    queuedCommandHandlingRef.current = true;
    void submitOrCancel(queuedCommand).finally(() => {
      queuedCommandHandlingRef.current = false;
      onQueuedCommandHandled?.();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queuedCommand, onQueuedCommandHandled]);

  return (
    <section className="conversation-pane">
      <AcpInteractionSurface
        sessionId={activeSession?.id ?? null}
        taskId={activeTask?.id ?? null}
        events={events}
        emptyMessage={emptyMessage(activeTask, activeSession)}
        loading={loading}
        running={isRunning}
        error={error}
        queuedComposerDraft={queuedComposerDraft}
        onApproved={async () => {
          await refreshWorkspace();
          await refreshTimeline();
        }}
        onCancel={cancelActiveSession}
        onOpenPath={onOpenPath}
        onQueuedComposerDraftHandled={onQueuedComposerDraftHandled}
        onReloadInput={reloadInput}
        onSendMessage={submitOrCancel}
      />
      {showHelp && (
        <article className="inline-card">
          <header>
            <strong>Slash commands</strong>
            <button type="button" onClick={() => setShowHelp(false)}>
              Close
            </button>
          </header>
          <ul>
            {SLASH_COMMANDS.map((command) => (
              <li key={command.command}>
                <code>{command.command}</code> {command.description}
              </li>
            ))}
          </ul>
        </article>
      )}
      {composerHint && <p className="pane-note pane-note--hint">{composerHint}</p>}
      <p className="status-line">{status}</p>
    </section>
  );
}

function emptyMessage(activeTask: TaskRecord | null, activeSession: SessionRecord | null) {
  if (!activeTask) return "Create a workspace to begin.";
  if (!activeSession) return "Send a message to create a session, or type /start to begin the outline loop.";
  if (activeSession.status === "idle") return "Session is ready. Type /start to begin the outline loop.";
  if (activeSession.status === "await_outline_approval") return "Review and approve the outline above to continue.";
  if (activeSession.status === "completed") return "Session complete. Create a new session to start again.";
  if (activeSession.status === "cancelled") return "Session was cancelled. Create a new session to start again.";
  return null;
}

function composerHintFor(activeSession: SessionRecord | null): string | null {
  if (!activeSession) return null;
  if (activeSession.status === "await_outline_approval") {
    return "The outline above needs your approval before the agent can continue.";
  }
  return null;
}

function idleSubmitHint(status: string): string {
  if (status === "idle") return "Type /start to begin the outline loop, or use a slash command.";
  if (status === "await_outline_approval") return "Approve the outline above to continue the loop.";
  if (status === "completed") return "Session is complete. Create a new session to continue writing.";
  if (status === "cancelled") return "Session was cancelled. Create a new session to continue.";
  return `Cannot send chat while session is ${status}. Try a slash command.`;
}

