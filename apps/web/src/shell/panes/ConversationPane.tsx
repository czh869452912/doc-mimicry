import { AssistantRuntimeProvider } from "@assistant-ui/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../api";
import type { SessionRecord, TaskRecord, TimelineEvent } from "../../types";
import { DocAgentComposer } from "../assistant/DocAgentComposer";
import { DocAgentThread } from "../assistant/DocAgentThread";
import { useDocAgentAssistantRuntime } from "../assistant/useDocAgentAssistantRuntime";
import { SLASH_COMMANDS, executeSlashCommand } from "../conversation/slashCommands";

interface ConversationPaneProps {
  activeSession: SessionRecord | null;
  activeTask: TaskRecord | null;
  ensureSession: () => Promise<SessionRecord | null>;
  events: TimelineEvent[];
  error: string | null;
  loading: boolean;
  onOpenPath: (path: string) => Promise<void>;
  onQueuedComposerDraftHandled?: () => void;
  onQueuedCommandHandled?: () => void;
  queuedComposerDraft?: string | null;
  queuedCommand?: string | null;
  refreshTimeline: () => Promise<unknown>;
  refreshWorkspace: () => Promise<unknown>;
}

export function ConversationPane({
  activeSession,
  activeTask,
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
}: ConversationPaneProps) {
  const [status, setStatus] = useState("");
  const [showHelp, setShowHelp] = useState(false);
  const eventsRef = useRef(events);

  useEffect(() => {
    eventsRef.current = events;
  }, [events]);

  const submitInput = useCallback(
    async (rawInput: string) => {
      const input = rawInput.trimEnd();
      if (!input) return;

      try {
        const commandResult = await executeSlashCommand(input, {
          activeTask,
          ensureSession,
          openArtifact: onOpenPath,
          openHelp: () => setShowHelp(true),
          refreshTimeline,
          refreshWorkspace,
        });
        if (!commandResult.handled) {
          const session = await ensureSession();
          if (!session) {
            setStatus("Create a workspace first.");
            return;
          }
          await api.sendMessage(session.id, input);
          await refreshTimeline();
          await refreshWorkspace();
          setStatus("");
          return;
        }
        setStatus(commandResult.message ?? "");
      } catch (caught) {
        setStatus(caught instanceof Error ? caught.message : "Conversation action failed.");
      }
    },
    [activeTask, ensureSession, onOpenPath, refreshTimeline, refreshWorkspace],
  );

  const reloadInput = useCallback(
    async (parentMessageId: string | null) => {
      const input = inputForReload(eventsRef.current, parentMessageId);
      if (!input) {
        setStatus("No previous user message to reload.");
        return;
      }
      await submitInput(input);
    },
    [submitInput],
  );

  const composerDisabled = !activeTask || !canSubmitComposerInput(activeSession);
  const runtime = useDocAgentAssistantRuntime({
    activeTaskId: activeTask?.id ?? null,
    disabled: composerDisabled,
    events,
    isRunning: Boolean(activeSession?.status?.startsWith("running")),
    onReloadInput: reloadInput,
    onSubmitInput: submitInput,
  });

  const queuedCommandHandlingRef = useRef(false);
  useEffect(() => {
    if (!queuedCommand || queuedCommandHandlingRef.current) return;
    queuedCommandHandlingRef.current = true;
    void submitInput(queuedCommand).finally(() => {
      queuedCommandHandlingRef.current = false;
      onQueuedCommandHandled?.();
    });
    // Intentionally omit submitInput — we only want to fire once per queuedCommand value.
    // submitInput identity changes on every session update (via ensureSession), but the
    // command is already captured in the closure when the effect first runs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queuedCommand, onQueuedCommandHandled]);

  return (
    <section className="conversation-pane aui-root">
      <AssistantRuntimeProvider runtime={runtime}>
        <DocAgentThread
          activeSessionId={activeSession?.id ?? null}
          emptyMessage={emptyMessage(activeTask, activeSession)}
          isLoading={loading}
          isRunning={Boolean(activeSession?.status?.startsWith("running"))}
          taskId={activeTask?.id ?? null}
          onApproved={async () => {
            await refreshWorkspace();
            await refreshTimeline();
          }}
          onOpenPath={onOpenPath}
          onReloadMessage={reloadInput}
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
        <DocAgentComposer
          disabled={composerDisabled}
          draftText={queuedComposerDraft}
          onDraftTextApplied={onQueuedComposerDraftHandled}
        />
      </AssistantRuntimeProvider>
      {error && <p className="pane-note pane-note--error">{error}</p>}
      <p className="status-line">{status}</p>
    </section>
  );
}

function emptyMessage(activeTask: TaskRecord | null, activeSession: SessionRecord | null) {
  if (!activeTask) return "Create a workspace to begin.";
  if (!activeSession) return "Send a message or run /start to create a session.";
  return null;
}

function canSubmitComposerInput(activeSession: SessionRecord | null) {
  if (!activeSession) return true;
  return ["idle", "draft_ready", "paused", "failed"].includes(activeSession.status);
}

function inputForReload(events: TimelineEvent[], parentMessageId: string | null) {
  const parentIndex = parentMessageId
    ? events.findIndex((event) => event.id === parentMessageId)
    : events.length;
  // When parentMessageId is null, parentIndex === events.length (intentionally out of bounds)
  // When parentMessageId refers to a message not found, parentIndex === -1
  if (parentIndex >= 0 && parentIndex < events.length) {
    const parentEvent = events[parentIndex];
    if (parentEvent.kind === "user_message" && parentEvent.summary.trim()) return parentEvent.summary;
  }
  const endIndex = parentIndex >= 0 ? parentIndex : events.length;
  for (let index = endIndex - 1; index >= 0; index -= 1) {
    const event = events[index];
    if (event.kind === "user_message" && event.summary.trim()) return event.summary;
  }
  return null;
}
