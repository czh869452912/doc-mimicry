import { MessageSquare, Sparkles } from "lucide-react";
import { useState } from "react";
import { LazyDraftEditor } from "../LazyDraftEditor";
import { MarkdownPreview } from "../MarkdownPreview";
import { useAutoSave } from "../useAutoSave";

interface DraftTabProps {
  activeSessionId: string | null;
  autoSaveEnabled?: boolean;
  draft: string;
  taskId: string | null;
  onDraftChange: (draft: string) => void;
  onReviseSelection?: (selectedText: string) => void;
  onSendSelectionToChat?: (selectedText: string) => void;
}

export function DraftTab({
  activeSessionId,
  autoSaveEnabled = true,
  draft,
  onDraftChange,
  onReviseSelection,
  onSendSelectionToChat,
  taskId,
}: DraftTabProps) {
  const [mode, setMode] = useState<"preview" | "source">("preview");
  const [selectedText, setSelectedText] = useState("");
  const saveState = useAutoSave(taskId, draft, autoSaveEnabled);

  return (
    <section className="draft-tab">
      <div className="editor-toolbar">
        <div className="segmented-control" role="group" aria-label="Draft mode">
          <button className={mode === "preview" ? "active" : ""} type="button" onClick={() => setMode("preview")}>
            Preview
          </button>
          <button className={mode === "source" ? "active" : ""} type="button" onClick={() => setMode("source")}>
            Source
          </button>
        </div>
        <button className="primary-button" type="button" disabled title="Checkpoint endpoint is not available yet">
          + Checkpoint
        </button>
        <span className="muted body-sm">last save · {saveState}</span>
      </div>
      <div className="draft-tab__body">
        {mode === "preview" ? (
          <MarkdownPreview markdown={draft} />
        ) : (
          <LazyDraftEditor markdown={draft} onChange={onDraftChange} onSelection={setSelectedText} />
        )}
      </div>
      {selectedText && activeSessionId && onSendSelectionToChat && onReviseSelection && (
        <div className="selection-bar">
          <button type="button" onClick={() => onSendSelectionToChat(selectedText)}>
            <MessageSquare size={14} /> Send to chat
          </button>
          <button type="button" onClick={() => onReviseSelection(selectedText)}>
            <Sparkles size={14} /> Revise selection
          </button>
        </div>
      )}
    </section>
  );
}
