import { Paperclip, Send, Square, X } from "lucide-react";
import { type ChangeEvent, type KeyboardEvent, useEffect, useRef, useState } from "react";
import { api } from "../../api";
import type { MessageAttachment } from "../../types";
import { DocAgentSlashCommands } from "./DocAgentSlashCommands";

interface PendingTextAttachment {
  file: File;
  id: string;
  name: string;
  text: string;
}

interface AcpComposerProps {
  disabled: boolean;
  draftText?: string | null;
  isRunning?: boolean;
  onCancel?: () => void;
  onDraftTextApplied?: () => void;
  onSend: (input: string, attachments?: MessageAttachment[]) => Promise<void>;
  taskId?: string | null;
}

export function AcpComposer({
  disabled,
  draftText,
  isRunning = false,
  onCancel,
  onDraftTextApplied,
  onSend,
  taskId = null,
}: AcpComposerProps) {
  const [text, setText] = useState("");
  const [attachments, setAttachments] = useState<PendingTextAttachment[]>([]);
  const [attachmentError, setAttachmentError] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!draftText) return;
    setText(draftText);
    inputRef.current?.focus();
    onDraftTextApplied?.();
  }, [draftText, onDraftTextApplied]);

  function selectCommand(command: string) {
    setText(`${command} `);
    inputRef.current?.focus();
  }

  async function submit() {
    const input = text.trimEnd();
    if (!input || disabled || isRunning) return;
    const nextAttachments = await importAttachments();
    setText("");
    setAttachments([]);
    setAttachmentError(null);
    await onSend(input, nextAttachments);
  }

  function keyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submit();
    }
  }

  async function addLocalAttachments(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    const nextAttachments = await Promise.all(
      files.map(async (file) => ({
        file,
        id: `${file.name}-${file.size}-${file.lastModified}`,
        name: file.name,
        text: await file.text(),
      })),
    );
    setAttachments((current) => [...current, ...nextAttachments]);
    event.target.value = "";
  }

  async function importAttachments(): Promise<MessageAttachment[]> {
    if (attachments.length === 0) return [];
    if (!taskId) {
      setAttachmentError("Create a workspace before attaching files.");
      return [];
    }
    return Promise.all(
      attachments.map(async (attachment) => {
        const imported = await api.importTextInput(taskId, attachment.name, attachment.text);
        return {
          name: attachment.name,
          markdown_path: imported.markdown_path,
          source_path: imported.source_path,
          conversion_report_path: imported.conversion_report_path,
        };
      }),
    );
  }

  return (
    <div className="acp-composer" aria-disabled={disabled}>
      <div className="acp-composer__input-wrap">
        {attachments.length > 0 && (
          <div className="acp-composer__attachments">
            {attachments.map((attachment) => (
              <span className="acp-attachment-chip" key={attachment.id}>
                <span>{attachment.name}</span>
                <button
                  type="button"
                  aria-label={`Remove ${attachment.name}`}
                  onClick={() => setAttachments((current) => current.filter((item) => item.id !== attachment.id))}
                >
                  <X size={12} />
                </button>
              </span>
            ))}
          </div>
        )}
        <textarea
          ref={inputRef}
          aria-label="Message"
          disabled={disabled}
          placeholder={isRunning ? "Agent is working" : "Message the agent, or type / for commands"}
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={keyDown}
        />
        <DocAgentSlashCommands query={text} onSelect={selectCommand} />
        {attachmentError && <p className="pane-note pane-note--error">{attachmentError}</p>}
      </div>
      <input ref={fileInputRef} className="sr-only" type="file" multiple onChange={addLocalAttachments} />
      <button
        type="button"
        className="acp-attach-button"
        disabled={disabled}
        aria-label="Attach file"
        onClick={() => fileInputRef.current?.click()}
      >
        <Paperclip size={15} />
      </button>
      {isRunning ? (
        <button type="button" className="acp-send-button acp-send-button--stop" aria-label="Stop the running agent" onClick={() => onCancel?.()}>
          <Square size={13} />
        </button>
      ) : (
        <button type="button" className="acp-send-button" aria-label="Send message" disabled={disabled} onClick={() => void submit()}>
          <Send size={15} />
        </button>
      )}
    </div>
  );
}
