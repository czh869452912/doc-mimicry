import { Send } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../../api";
import type { SessionRecord, TaskRecord } from "../../types";
import { SLASH_COMMANDS, executeSlashCommand } from "../conversation/slashCommands";
import type { Presentation } from "../conversation/timelinePresentation";
import { ApprovalCard } from "../conversation/cards/ApprovalCard";
import { ArtifactCard } from "../conversation/cards/ArtifactCard";
import { ChecklistCard } from "../conversation/cards/ChecklistCard";
import { OutlineCard } from "../conversation/cards/OutlineCard";

interface ConversationPaneProps {
  activeSession: SessionRecord | null;
  activeTask: TaskRecord | null;
  ensureSession: () => Promise<SessionRecord | null>;
  error: string | null;
  loading: boolean;
  onOpenPath: (path: string) => Promise<void>;
  onQueuedCommandHandled?: () => void;
  presentations: Presentation[];
  queuedCommand?: string | null;
  refreshTimeline: () => Promise<unknown>;
  refreshWorkspace: () => Promise<unknown>;
}

export function ConversationPane({
  activeSession,
  activeTask,
  ensureSession,
  error,
  loading,
  onQueuedCommandHandled,
  onOpenPath,
  presentations,
  queuedCommand,
  refreshTimeline,
  refreshWorkspace,
}: ConversationPaneProps) {
  const [composer, setComposer] = useState("");
  const [status, setStatus] = useState("");
  const [showHelp, setShowHelp] = useState(false);

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
        await api.sendMessage(session.id, input);
        await refreshWorkspace();
        await refreshTimeline();
      }
      setStatus(commandResult.message ?? "Message processed.");
    } catch (caught) {
      setStatus(caught instanceof Error ? caught.message : "Conversation action failed.");
    }
  }

  async function submitComposer() {
    const input = composer;
    setComposer("");
    await submitInput(input);
  }

  return (
    <section className="conversation-pane">
      <div className="conversation-stream">
        {!activeTask && <div className="conversation-empty">Create a workspace to begin.</div>}
        {activeTask && !activeSession && (
          <div className="conversation-empty">Send a message or run /start to create a session.</div>
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
        {presentations.map((presentation) => (
          <StreamItem
            activeSessionId={activeSession?.id ?? null}
            key={presentation.kind === "card" ? presentation.payload.id : presentation.event.id}
            presentation={presentation}
            taskId={activeTask?.id ?? null}
            onApproved={async () => {
              await refreshWorkspace();
              await refreshTimeline();
            }}
            onOpenPath={onOpenPath}
          />
        ))}
      </div>
      {error && <p className="pane-note pane-note--error">{error}</p>}
      {loading && <p className="pane-note">Refreshing timeline...</p>}
      <p className="status-line">{status}</p>
      <form
        className="composer"
        onSubmit={(event) => {
          event.preventDefault();
          void submitComposer();
        }}
      >
        <textarea
          aria-label="Message"
          placeholder="Message the agent, or type / for commands"
          value={composer}
          onChange={(event) => setComposer(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              void submitComposer();
            }
          }}
        />
        <button className="send-button" type="submit" disabled={!activeTask}>
          <Send size={15} />
        </button>
      </form>
    </section>
  );
}

function StreamItem({
  activeSessionId,
  onApproved,
  onOpenPath,
  presentation,
  taskId,
}: {
  activeSessionId: string | null;
  onApproved: () => Promise<void>;
  onOpenPath: (path: string) => Promise<void>;
  presentation: Presentation;
  taskId: string | null;
}) {
  if (presentation.kind === "message") {
    return <article className={`message message--${presentation.role}`}>{presentation.body}</article>;
  }
  if (presentation.kind === "pill") {
    return (
      <article className="event-pill-row">
        <span className="event-pill" data-category={presentation.category}>
          {presentation.event.kind}
        </span>
        <span>{presentation.summary}</span>
        {presentation.meta && <small>{presentation.meta}</small>}
      </article>
    );
  }
  if (presentation.cardType === "outline") {
    return (
      <OutlineCard
        event={presentation.payload}
        sessionId={activeSessionId}
        taskId={taskId}
        onApproved={onApproved}
        onOpenPath={onOpenPath}
      />
    );
  }
  if (presentation.cardType === "checklist") {
    return <ChecklistCard event={presentation.payload} onOpenPath={onOpenPath} />;
  }
  if (presentation.cardType === "artifact") {
    return <ArtifactCard event={presentation.payload} onOpenPath={onOpenPath} />;
  }
  return <ApprovalCard event={presentation.payload} />;
}
