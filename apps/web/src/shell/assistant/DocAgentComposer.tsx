import { ComposerPrimitive, useAui } from "@assistant-ui/react";
import { Send } from "lucide-react";
import { useRef, useState } from "react";
import { DocAgentSlashCommands } from "./DocAgentSlashCommands";

interface DocAgentComposerProps {
  disabled: boolean;
}

export function DocAgentComposer({ disabled }: DocAgentComposerProps) {
  const aui = useAui();
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const [query, setQuery] = useState("");

  function selectCommand(command: string) {
    const input = inputRef.current;
    if (!input) return;
    const nextValue = `${command} `;
    aui.composer().setText(nextValue);
    input.focus();
    setQuery(nextValue);
  }

  return (
    <ComposerPrimitive.Root className="aui-composer" aria-disabled={disabled}>
      <div className="aui-composer__input-wrap">
        <ComposerPrimitive.Input
          ref={inputRef}
          aria-label="Message"
          disabled={disabled}
          placeholder="Message the agent, or type / for commands"
          submitMode="enter"
          onChange={(event) => setQuery(event.currentTarget.value)}
        />
        <DocAgentSlashCommands query={query} onSelect={selectCommand} />
      </div>
      <ComposerPrimitive.Send className="aui-send-button" disabled={disabled}>
        <Send size={15} />
      </ComposerPrimitive.Send>
    </ComposerPrimitive.Root>
  );
}
