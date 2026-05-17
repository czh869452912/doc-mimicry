import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE, api } from "../../api";
import type { AcpEvent, MessageAttachment, SessionRecord, TaskRecord } from "../../types";
import { type AcpPermissionDecision, AcpInteractionSurface } from "../acp/AcpInteractionSurface";
import { AcpUiEmbed } from "../acp/AcpUiEmbed";
import { configuredAcpUiUrl } from "../acp/acpUiEmbedUrl";
import { findReloadInput } from "../acp/acpEvents";
import { SLASH_COMMANDS, executeSlashCommand } from "../conversation/slashCommands";

interface ConversationPaneProps {
  activeSession: SessionRecord | null;
  activeTask: TaskRecord | null;
  createSession: () => Promise<SessionRecord | null>;
  createCheckpoint?: () => Promise<unknown>;
  ensureSession: () => Promise<SessionRecord | null>;
  events: AcpEvent[];
  error: string | null;
  externalStatus?: string;
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
  createCheckpoint,
  createSession,
  ensureSession,
  events,
  error,
  externalStatus = "",
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
  const [statusSource, setStatusSource] = useState<"internal" | "external">("internal");
  const [showHelp, setShowHelp] = useState(false);
  const eventsRef = useRef(events);
  const cancellationInFlightRef = useRef(false);
  const isRunning = Boolean(activeSession?.status?.startsWith("running"));
  eventsRef.current = events;

  useEffect(() => {
    if (externalStatus) setStatusSource("external");
  }, [externalStatus]);

  const setInternalStatus = useCallback((message: string) => {
    setStatusSource("internal");
    setStatus(message);
  }, []);

  const cancelActiveSession = useCallback(async () => {
    if (!activeSession || cancellationInFlightRef.current) return;
    cancellationInFlightRef.current = true;
    try {
      await api.cancelSession(activeSession.id);
      await refreshTimeline();
      await refreshSessions?.();
      setInternalStatus("Cancelled.");
    } catch (caught) {
      setInternalStatus(caught instanceof Error ? caught.message : "Cancel failed.");
    } finally {
      cancellationInFlightRef.current = false;
    }
  }, [activeSession, refreshTimeline, refreshSessions, setInternalStatus]);

  const submitOrCancel = useCallback(
    async (rawInput: string, attachments: MessageAttachment[] = []) => {
      const input = rawInput.trimEnd();
      if (isRunning && activeSession) {
        if (input) {
          setInternalStatus("Agent is working.");
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
          createCheckpoint,
          createSession,
          ensureSession,
          openArtifact: onOpenPath,
          openHelp: () => setShowHelp(true),
          refreshSessions,
          refreshTimeline,
          refreshWorkspace,
        });
        if (commandResult.handled) {
          setInternalStatus(commandResult.message ?? "");
          return;
        }
        if (activeSession && ["completed", "cancelled"].includes(activeSession.status)) {
          setInternalStatus(idleSubmitHint(activeSession.status));
          return;
        }
        const session = await ensureSession();
        if (!session) {
          setInternalStatus("Create a workspace first.");
          return;
        }
        await api.sendMessage(session.id, input, attachments);
        await refreshTimeline();
        await refreshWorkspace();
        await refreshSessions?.();
        setInternalStatus("");
      } catch (caught) {
        setInternalStatus(caught instanceof Error ? caught.message : "Conversation action failed.");
      }
    },
    [
      isRunning,
      activeSession,
      cancelActiveSession,
      activeTask,
      createCheckpoint,
      createSession,
      ensureSession,
      onOpenPath,
      refreshTimeline,
      refreshWorkspace,
      refreshSessions,
      setInternalStatus,
    ],
  );

  const reloadInput = useCallback(
    async (parentEventId: string | null) => {
      const input = findReloadInput(eventsRef.current, parentEventId);
      if (!input) {
        setInternalStatus("No previous user message to reload.");
        return;
      }
      await submitOrCancel(input);
    },
    [setInternalStatus, submitOrCancel],
  );

  const answerPermission = useCallback(
    async (requestId: string, decision: AcpPermissionDecision) => {
      if (!activeSession) {
        setInternalStatus("Create a session before answering permissions.");
        return;
      }
      try {
        await api.answerPermission(activeSession.id, requestId, decision);
        await refreshTimeline();
        await refreshSessions?.();
        setInternalStatus("");
      } catch (caught) {
        setInternalStatus(caught instanceof Error ? caught.message : "Permission response failed.");
      }
    },
    [activeSession, refreshTimeline, refreshSessions, setInternalStatus],
  );

  const attachContext = useCallback(
    async (_attachments: MessageAttachment[]) => {
      await refreshWorkspace();
    },
    [refreshWorkspace],
  );

  const composerDisabled = !activeTask;
  const composerHint = composerHintFor(activeSession);
  const acpUiUrl = configuredAcpUiUrl();

  const queuedCommandHandlingRef = useRef(false);
  useEffect(() => {
    if (!queuedCommand || queuedCommandHandlingRef.current) return;
    queuedCommandHandlingRef.current = true;
    void submitOrCancel(queuedCommand).finally(() => {
      queuedCommandHandlingRef.current = false;
      onQueuedCommandHandled?.();
    });
    // submitOrCancel is intentionally omitted so queued palette commands run once per queued command,
    // not again when workspace refresh callbacks receive new identities.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queuedCommand, onQueuedCommandHandled]);

  return (
    <section className="conversation-pane">
      {acpUiUrl ? (
        <AcpUiEmbed
          acpUiUrl={acpUiUrl}
          apiBase={API_BASE}
          sessionId={activeSession?.id ?? null}
          taskId={activeTask?.id ?? null}
          workspaceRoot={activeTask?.workspace_root ?? null}
        />
      ) : (
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
            await refreshSessions?.();
          }}
          onAnswerPermission={answerPermission}
          onAttachContext={attachContext}
          onCancel={cancelActiveSession}
          onOpenPath={onOpenPath}
          onQueuedComposerDraftHandled={onQueuedComposerDraftHandled}
          onReloadInput={reloadInput}
          onSendMessage={submitOrCancel}
        />
      )}
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
      <p className="status-line">{statusSource === "external" && externalStatus ? externalStatus : status}</p>
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

