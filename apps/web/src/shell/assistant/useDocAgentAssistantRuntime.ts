import type { StartRunConfig } from "@assistant-ui/core";
import { useExternalStoreRuntime, type AppendMessage, type ThreadMessage } from "@assistant-ui/react";
import { useMemo, useRef } from "react";
import type { TimelineEvent } from "../../types";
import { createDocAgentTextAttachmentAdapter } from "./docAgentAttachmentAdapter";
import { mapTimelineEventsToAssistantMessages } from "./docAgentAssistantMessages";
import type { MessageAttachment } from "../../types";

interface UseDocAgentAssistantRuntimeOptions {
  activeTaskId: string | null;
  events: TimelineEvent[];
  isRunning: boolean;
  onCancel?: () => Promise<void>;
  onReloadInput?: (parentMessageId: string | null, config: StartRunConfig) => Promise<void>;
  onSubmitInput: (input: string, attachments?: MessageAttachment[]) => Promise<void>;
}

type ImportedAttachmentStore = Record<string, MessageAttachment[]>;

export function addImportedAttachmentForTask(
  store: ImportedAttachmentStore,
  taskId: string | null,
  reference: MessageAttachment,
) {
  if (!taskId) return store;
  return {
    ...store,
    [taskId]: [...(store[taskId] ?? []), reference],
  };
}

export function takeImportedAttachmentsForTask(
  store: ImportedAttachmentStore,
  taskId: string | null,
) {
  if (!taskId) return { nextStore: store, attachments: [] as MessageAttachment[] };
  const { [taskId]: attachments = [], ...rest } = store;
  return { nextStore: rest, attachments };
}

export function useDocAgentAssistantRuntime({
  activeTaskId,
  events,
  isRunning,
  onCancel,
  onReloadInput,
  onSubmitInput,
}: UseDocAgentAssistantRuntimeOptions) {
  const messages = useMemo(() => mapTimelineEventsToAssistantMessages(events), [events]);
  const importedAttachmentReferencesRef = useRef<ImportedAttachmentStore>({});

  const attachmentAdapter = useMemo(
    () =>
      createDocAgentTextAttachmentAdapter({
        taskId: activeTaskId,
        onImported: (reference) => {
          importedAttachmentReferencesRef.current = addImportedAttachmentForTask(
            importedAttachmentReferencesRef.current,
            activeTaskId,
            reference,
          );
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
    onCancel,
    onNew: async (message: AppendMessage) => {
      const result = takeImportedAttachmentsForTask(importedAttachmentReferencesRef.current, activeTaskId);
      importedAttachmentReferencesRef.current = result.nextStore;
      await onSubmitInput(textFromAppendMessage(message), result.attachments);
    },
    onReload: async (parentId: string | null, config: StartRunConfig) => {
      await onReloadInput?.(parentId, config);
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
