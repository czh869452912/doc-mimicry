import { Paperclip, Send, Square, X } from "lucide-react";
import { type ChangeEvent, type KeyboardEvent, useEffect, useRef, useState } from "react";
import { api } from "../../api";
import type { MessageAttachment } from "../../types";
import { DocAgentSlashCommands } from "./DocAgentSlashCommands";

interface PendingAttachment {
  file: File;
  id: string;
  name: string;
}

interface AcpComposerProps {
  disabled: boolean;
  draftText?: string | null;
  isRunning?: boolean;
  onAttachContext?: (attachments: MessageAttachment[]) => Promise<void>;
  onCancel?: () => void | Promise<void>;
  onDraftTextApplied?: () => void;
  onSend: (input: string, attachments?: MessageAttachment[]) => Promise<void>;
  taskId?: string | null;
}

export function AcpComposer({
  disabled,
  draftText,
  isRunning = false,
  onAttachContext,
  onCancel,
  onDraftTextApplied,
  onSend,
  taskId = null,
}: AcpComposerProps) {
  const [text, setText] = useState("");
  const [attachments, setAttachments] = useState<PendingAttachment[]>([]);
  const [attachmentError, setAttachmentError] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

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
    setAttachmentError(null);
    let nextAttachments: MessageAttachment[];
    try {
      nextAttachments = await importAttachments();
    } catch (caught) {
      setAttachmentError(caught instanceof Error ? caught.message : "Attachment import failed.");
      return;
    }
    if (nextAttachments.length > 0) {
      await onAttachContext?.(nextAttachments);
    }
    setText("");
    setAttachments([]);
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
    const nextAttachments = files.map((file) => ({
      file,
      id: `${file.name}-${file.size}-${file.lastModified}`,
      name: file.name,
    }));
    setAttachments((current) => [...current, ...nextAttachments]);
    event.target.value = "";
  }

  async function importAttachments(): Promise<MessageAttachment[]> {
    if (attachments.length === 0) return [];
    if (!taskId) {
      setAttachmentError("Create a workspace before attaching files.");
      return [];
    }
    const imported = await Promise.all(attachments.map((attachment) => api.importFileInput(taskId, attachment.file)));
    const failed = imported.filter((item) => !item.markdown_path);
    if (failed.length > 0) {
      setAttachmentError(`${failed.map((item) => item.original_filename).join(", ")} could not be converted.`);
    }
    return imported
      .filter((item) => item.markdown_path)
      .map((item) => ({
        name: item.original_filename,
        markdown_path: item.markdown_path as string,
        source_path: item.source_path,
        conversion_report_path: item.conversion_report_path,
      }));
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
      <label
        className={`acp-attach-button${disabled ? " acp-attach-button--disabled" : ""}`}
        aria-label="Attach file"
        aria-disabled={disabled}
        role="button"
        tabIndex={disabled ? -1 : 0}
      >
        <input
          aria-label="Choose attachment file"
          className="acp-file-input"
          type="file"
          multiple
          disabled={disabled}
          onChange={addLocalAttachments}
        />
        <Paperclip size={15} />
      </label>
      {isRunning ? (
        <button type="button" className="acp-send-button acp-send-button--stop" aria-label="Stop the running agent" onClick={() => void onCancel?.()}>
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
