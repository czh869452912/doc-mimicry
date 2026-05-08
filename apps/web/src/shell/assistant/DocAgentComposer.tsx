import { ComposerPrimitive } from "@assistant-ui/react";
import { Send } from "lucide-react";

interface DocAgentComposerProps {
  disabled: boolean;
}

export function DocAgentComposer({ disabled }: DocAgentComposerProps) {
  return (
    <ComposerPrimitive.Root className="aui-composer" aria-disabled={disabled}>
      <ComposerPrimitive.Input
        aria-label="Message"
        disabled={disabled}
        placeholder="Message the agent, or type / for commands"
        submitMode="enter"
      />
      <ComposerPrimitive.Send className="aui-send-button" disabled={disabled}>
        <Send size={15} />
      </ComposerPrimitive.Send>
    </ComposerPrimitive.Root>
  );
}
