import { useExternalStoreRuntime, type AppendMessage, type ThreadMessage } from "@assistant-ui/react";
import { useEffect, useMemo, useRef } from "react";
import type { TimelineEvent } from "../../types";
import { createDocAgentTextAttachmentAdapter } from "./docAgentAttachmentAdapter";
import { mapTimelineEventsToAssistantMessages } from "./docAgentAssistantMessages";
import type { MessageAttachment } from "../../types";

interface UseDocAgentAssistantRuntimeOptions {
  activeTaskId: string | null;
  events: TimelineEvent[];
  isRunning: boolean;
  onReloadInput?: (parentMessageId: string | null) => Promise<void>;
  onSubmitInput: (input: string, attachments?: MessageAttachment[]) => Promise<void>;
}

export function useDocAgentAssistantRuntime({
  activeTaskId,
  events,
  isRunning,
  onReloadInput,
  onSubmitInput,
}: UseDocAgentAssistantRuntimeOptions) {
  const messages = useMemo(() => mapTimelineEventsToAssistantMessages(events), [events]);
  const importedAttachmentReferencesRef = useRef<MessageAttachment[]>([]);

  useEffect(() => {
    importedAttachmentReferencesRef.current = [];
  }, [activeTaskId]);

  const attachmentAdapter = useMemo(
    () =>
      createDocAgentTextAttachmentAdapter({
        taskId: activeTaskId,
        onImported: (reference) => {
          importedAttachmentReferencesRef.current = [...importedAttachmentReferencesRef.current, reference];
        },
      }),
    [activeTaskId],
  );

  return useExternalStoreRuntime<ThreadMessage>({
    adapters: {
      attachments: attachmentAdapter,
    },
    isRunning,
    messages,
    onNew: async (message: AppendMessage) => {
      const attachments = importedAttachmentReferencesRef.current;
      importedAttachmentReferencesRef.current = [];
      await onSubmitInput(textFromAppendMessage(message), attachments);
    },
    onReload: async (parentId: string | null) => {
      await onReloadInput?.(parentId);
    },
    unstable_capabilities: { copy: true },
  });
}

function textFromAppendMessage(message: AppendMessage): string {
  const contentText = message.content
    .filter((part): part is Extract<(typeof message.content)[number], { type: "text" }> => part.type === "text")
    .map((part) => part.text)
    .join("\n");
  return contentText;
}
