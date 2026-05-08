import {
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
  taskId: string | null;
  onApproved: () => Promise<void>;
  onOpenPath: (path: string) => Promise<void>;
}

export function DocAgentThread({
  activeSessionId,
  emptyMessage,
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
      </ThreadPrimitive.Viewport>
    </ThreadPrimitive.Root>
  );
}

function UserMessage() {
  return (
    <MessagePrimitive.Root className="aui-message aui-message--user">
      <MessagePrimitive.Content components={{ Text: TextPart }} />
    </MessagePrimitive.Root>
  );
}

function AssistantMessage(props: Omit<DocAgentThreadProps, "emptyMessage">) {
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
}: DataMessagePartProps<DocAgentAssistantData> & Omit<DocAgentThreadProps, "emptyMessage">) {
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
