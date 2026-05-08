import {
  ActionBarPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  type DataMessagePartProps,
  type TextMessagePartProps,
} from "@assistant-ui/react";
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
            AssistantMessage: () => (
              <AssistantMessage
                activeSessionId={activeSessionId}
                taskId={taskId}
                onApproved={onApproved}
                onOpenPath={onOpenPath}
              />
            ),
          }}
        />
        {(isLoading || isRunning) && (
          <div className="aui-thread-status" role="status">
            {isRunning ? "Agent is working..." : "Refreshing timeline..."}
          </div>
        )}
      </ThreadPrimitive.Viewport>
    </ThreadPrimitive.Root>
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

function AssistantMessage(props: MessagePartHandlerProps) {
  return (
    <MessagePrimitive.Root className="aui-message aui-message--assistant">
      <MessagePrimitive.Content
        components={{
          Text: TextPart,
          data: {
            by_name: {
              "docagent.event-pill": (part) => <DataPart {...part} {...props} />,
              "docagent.outline-card": (part) => <DataPart {...part} {...props} />,
              "docagent.checklist-card": (part) => <DataPart {...part} {...props} />,
              "docagent.artifact-card": (part) => <DataPart {...part} {...props} />,
              "docagent.approval-card": (part) => <DataPart {...part} {...props} />,
            },
          },
        }}
      />
      <MessageActions />
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

function MessageActions() {
  return (
    <ActionBarPrimitive.Root className="aui-message-actions">
      <ActionBarPrimitive.Copy className="aui-message-action" aria-label="Copy text">
        Copy
      </ActionBarPrimitive.Copy>
    </ActionBarPrimitive.Root>
  );
}
