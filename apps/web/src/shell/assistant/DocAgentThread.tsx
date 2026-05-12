import {
  ActionBarPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  type DataMessagePartProps,
  type TextMessagePartProps,
} from "@assistant-ui/react";
import { createContext, useContext } from "react";
import type { DocAgentAssistantData } from "./docAgentAssistantMessages";
import { DocAgentMessagePart } from "./DocAgentMessageParts";

interface DocAgentThreadProps {
  activeSessionId: string | null;
  emptyMessage: string | null;
  isLoading: boolean;
  isRunning: boolean;
  taskId: string | null;
  onApproved: () => Promise<void>;
  onOpenPath: (path: string) => Promise<void>;
}

const DocAgentThreadContext = createContext<{
  activeSessionId: string | null;
  taskId: string | null;
  onApproved: () => Promise<void>;
  onOpenPath: (path: string) => Promise<void>;
} | null>(null);

function useDocAgentThreadContext() {
  const ctx = useContext(DocAgentThreadContext);
  if (!ctx) throw new Error("DocAgentThreadContext not found");
  return ctx;
}

export function DocAgentThread({
  activeSessionId,
  emptyMessage,
  isLoading,
  isRunning,
  onApproved,
  onOpenPath,
  taskId,
}: DocAgentThreadProps) {
  return (
    <DocAgentThreadContext.Provider
      value={{
        activeSessionId,
        taskId,
        onApproved,
        onOpenPath,
      }}
    >
      <ThreadPrimitive.Root className="aui-thread">
        <ThreadPrimitive.Viewport className="aui-thread-viewport">
          {emptyMessage && (
            <ThreadPrimitive.Empty>
              <div className="conversation-empty">{emptyMessage}</div>
            </ThreadPrimitive.Empty>
          )}
          <ThreadPrimitive.Messages
            components={{
              UserMessage: UserMessage,
              AssistantMessage: AssistantMessage,
            }}
          />
          {(isLoading || isRunning) && (
            <div className="aui-thread-status" role="status">
              {isRunning ? "Agent is working..." : "Refreshing timeline..."}
            </div>
          )}
        </ThreadPrimitive.Viewport>
      </ThreadPrimitive.Root>
    </DocAgentThreadContext.Provider>
  );
}

function UserMessage() {
  return (
    <MessagePrimitive.Root className="aui-message aui-message--user">
      <MessagePrimitive.Content components={{ Text: TextPart }} />
      <MessageActions />
    </MessagePrimitive.Root>
  );
}

type MessagePartHandlerProps = Omit<DocAgentThreadProps, "emptyMessage" | "isLoading" | "isRunning">;

function AssistantMessage() {
  const { activeSessionId, taskId, onApproved, onOpenPath } = useDocAgentThreadContext();

  return (
    <MessagePrimitive.Root className="aui-message aui-message--assistant">
      <MessagePrimitive.Content
        components={{
          Text: TextPart,
          data: {
            by_name: {
              "docagent.tool-call": (part) => <DataPart {...part} activeSessionId={activeSessionId} taskId={taskId} onApproved={onApproved} onOpenPath={onOpenPath} />,
              "docagent.outline-card": (part) => <DataPart {...part} activeSessionId={activeSessionId} taskId={taskId} onApproved={onApproved} onOpenPath={onOpenPath} />,
              "docagent.checklist-card": (part) => <DataPart {...part} activeSessionId={activeSessionId} taskId={taskId} onApproved={onApproved} onOpenPath={onOpenPath} />,
              "docagent.artifact-card": (part) => <DataPart {...part} activeSessionId={activeSessionId} taskId={taskId} onApproved={onApproved} onOpenPath={onOpenPath} />,
              "docagent.approval-card": (part) => <DataPart {...part} activeSessionId={activeSessionId} taskId={taskId} onApproved={onApproved} onOpenPath={onOpenPath} />,
            },
          },
        }}
      />
      <MessageActions canReload />
    </MessagePrimitive.Root>
  );
}

function TextPart({ text }: TextMessagePartProps) {
  return <p className="aui-message-text">{text}</p>;
}

function DataPart({
  activeSessionId,
  data,
  onApproved,
  onOpenPath,
  taskId,
}: DataMessagePartProps<DocAgentAssistantData> & MessagePartHandlerProps) {
  return (
    <DocAgentMessagePart
      activeSessionId={activeSessionId}
      data={data}
      taskId={taskId}
      onApproved={onApproved}
      onOpenPath={onOpenPath}
    />
  );
}

function MessageActions({
  canReload = false,
}: {
  canReload?: boolean;
}) {
  return (
    <ActionBarPrimitive.Root className="aui-message-actions">
      <ActionBarPrimitive.Copy className="aui-message-action" aria-label="Copy text">
        Copy
      </ActionBarPrimitive.Copy>
      {canReload && (
        <ActionBarPrimitive.Reload className="aui-message-action" aria-label="Reload response">
          Reload
        </ActionBarPrimitive.Reload>
      )}
    </ActionBarPrimitive.Root>
  );
}
