import { useExternalStoreRuntime, type AppendMessage, type ThreadMessage } from "@assistant-ui/react";
import { useEffect, useMemo, useRef } from "react";
import type { TimelineEvent } from "../../types";
import { createDocAgentTextAttachmentAdapter } from "./docAgentAttachmentAdapter";
import { mapTimelineEventsToAssistantMessages } from "./docAgentAssistantMessages";

interface UseDocAgentAssistantRuntimeOptions {
  activeTaskId: string | null;
  disabled: boolean;
  events: TimelineEvent[];
  isRunning: boolean;
  onReloadInput?: (parentMessageId: string | null) => Promise<void>;
  onSubmitInput: (input: string) => Promise<void>;
}

export function useDocAgentAssistantRuntime({
  activeTaskId,
  disabled,
  events,
  isRunning,
  onReloadInput,
  onSubmitInput,
}: UseDocAgentAssistantRuntimeOptions) {
  const messages = useMemo(() => mapTimelineEventsToAssistantMessages(events), [events]);
  const importedAttachmentReferencesRef = useRef<string[]>([]);

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
    isDisabled: disabled,
    isRunning,
    messages,
    onNew: async (message: AppendMessage) => {
      const references = importedAttachmentReferencesRef.current;
      importedAttachmentReferencesRef.current = [];
      await onSubmitInput(textFromAppendMessage(message, references));
    },
    onReload: async (parentId: string | null) => {
      await onReloadInput?.(parentId);
    },
    unstable_capabilities: { copy: true },
  });
}

function textFromAppendMessage(message: AppendMessage, attachmentReferences: string[] = []): string {
  const contentText = message.content
    .filter((part): part is Extract<(typeof message.content)[number], { type: "text" }> => part.type === "text")
    .map((part) => part.text)
    .join("\n");
  return [...[contentText], ...attachmentReferences].filter(Boolean).join("\n");
}
