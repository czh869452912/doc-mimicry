import { AssistantRuntimeProvider } from "@assistant-ui/react";
import { useEffect, useState } from "react";
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
  onQueuedCommandHandled?: () => void;
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
  onQueuedCommandHandled,
  onOpenPath,
  queuedCommand,
  refreshTimeline,
  refreshWorkspace,
}: ConversationPaneProps) {
  const [status, setStatus] = useState("");
  const [showHelp, setShowHelp] = useState(false);
  const runtime = useDocAgentAssistantRuntime({
    disabled: !activeTask,
    events,
    isRunning: Boolean(activeSession?.status?.startsWith("running")),
    onSubmitInput: submitInput,
  });

  useEffect(() => {
    if (!queuedCommand) return;
    void submitInput(queuedCommand).finally(() => {
      onQueuedCommandHandled?.();
    });
  }, [queuedCommand]);

  async function submitInput(rawInput: string) {
    const input = rawInput.trimEnd();
    if (!input) return;
    setStatus("Working...");

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
        const result = await api.sendMessage(session.id, input);
        await refreshTimeline();
        if (result.accepted) {
          setStatus("Working...");
          return;
        }
        await refreshWorkspace();
      }
      setStatus(commandResult.message ?? "Message processed.");
    } catch (caught) {
      setStatus(caught instanceof Error ? caught.message : "Conversation action failed.");
    }
  }

  return (
    <section className="conversation-pane aui-root">
      <AssistantRuntimeProvider runtime={runtime}>
        <DocAgentThread
          activeSessionId={activeSession?.id ?? null}
          emptyMessage={emptyMessage(activeTask, activeSession)}
          taskId={activeTask?.id ?? null}
          onApproved={async () => {
            await refreshWorkspace();
            await refreshTimeline();
          }}
          onOpenPath={onOpenPath}
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
        <DocAgentComposer disabled={!activeTask} />
      </AssistantRuntimeProvider>
      {error && <p className="pane-note pane-note--error">{error}</p>}
      {loading && <p className="pane-note">Refreshing timeline...</p>}
      <p className="status-line">{status}</p>
    </section>
  );
}

function emptyMessage(activeTask: TaskRecord | null, activeSession: SessionRecord | null) {
  if (!activeTask) return "Create a workspace to begin.";
  if (!activeSession) return "Send a message or run /start to create a session.";
  return null;
}
