import { useExternalStoreRuntime, type AppendMessage, type ThreadMessage } from "@assistant-ui/react";
import { useMemo } from "react";
import type { TimelineEvent } from "../../types";
import { mapTimelineEventsToAssistantMessages } from "./docAgentAssistantMessages";

interface UseDocAgentAssistantRuntimeOptions {
  disabled: boolean;
  events: TimelineEvent[];
  isRunning: boolean;
  onReloadInput?: (parentMessageId: string | null) => Promise<void>;
  onSubmitInput: (input: string) => Promise<void>;
}

export function useDocAgentAssistantRuntime({
  disabled,
  events,
  isRunning,
  onReloadInput,
  onSubmitInput,
}: UseDocAgentAssistantRuntimeOptions) {
  const messages = useMemo(() => mapTimelineEventsToAssistantMessages(events), [events]);

  return useExternalStoreRuntime<ThreadMessage>({
    isDisabled: disabled,
    isRunning,
    messages,
    onNew: async (message: AppendMessage) => {
      await onSubmitInput(textFromAppendMessage(message));
    },
    onReload: async (parentId: string | null) => {
      await onReloadInput?.(parentId);
    },
    unstable_capabilities: { copy: true },
  });
}

function textFromAppendMessage(message: AppendMessage): string {
  return message.content
    .filter((part): part is Extract<(typeof message.content)[number], { type: "text" }> => part.type === "text")
    .map((part) => part.text)
    .join("\n");
}
