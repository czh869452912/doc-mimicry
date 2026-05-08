import { AttachmentPrimitive, ComposerPrimitive, useAui } from "@assistant-ui/react";
import { Paperclip, Send, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { DocAgentSlashCommands } from "./DocAgentSlashCommands";

interface DocAgentComposerProps {
  disabled: boolean;
  draftText?: string | null;
  onDraftTextApplied?: () => void;
}

export function DocAgentComposer({ disabled, draftText, onDraftTextApplied }: DocAgentComposerProps) {
  const aui = useAui();
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    if (!draftText) return;
    aui.composer().setText(draftText);
    inputRef.current?.focus();
    setQuery(draftText);
    onDraftTextApplied?.();
  }, [aui, draftText, onDraftTextApplied]);

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
      <ComposerPrimitive.AttachmentDropzone className="aui-composer__dropzone">
        <div className="aui-composer__input-wrap">
          <ComposerPrimitive.Attachments>
            {({ attachment }) => (
              <AttachmentPrimitive.Root
                className="aui-attachment-chip"
                data-status={attachment.status.type}
              >
                <AttachmentPrimitive.Name />
                <AttachmentPrimitive.Remove aria-label={`Remove ${attachment.name}`}>
                  <X size={12} />
                </AttachmentPrimitive.Remove>
              </AttachmentPrimitive.Root>
            )}
          </ComposerPrimitive.Attachments>
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
      </ComposerPrimitive.AttachmentDropzone>
      <ComposerPrimitive.AddAttachment
        className="aui-attach-button"
        disabled={disabled}
        aria-label="Attach file"
        multiple
      >
        <Paperclip size={15} />
      </ComposerPrimitive.AddAttachment>
      <ComposerPrimitive.Send className="aui-send-button" disabled={disabled}>
        <Send size={15} />
      </ComposerPrimitive.Send>
    </ComposerPrimitive.Root>
  );
}
