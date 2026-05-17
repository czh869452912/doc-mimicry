import { MessageSquare, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { LazyDraftEditor } from "../LazyDraftEditor";
import { LazyMarkdownPreview } from "../LazyMarkdownPreview";
import { type SaveState, useAutoSave } from "../useAutoSave";

interface DraftTabProps {
  activeSessionId: string | null;
  autoSaveEnabled?: boolean;
  draft: string;
  checkpointDisabled?: boolean;
  checkpointPending?: boolean;
  taskId: string | null;
  serverDraft?: string;
  onCreateCheckpoint?: (
    draft: string,
    lastSavedMarkdown: string,
  ) => Promise<boolean | string | void> | boolean | string | void;
  onDraftChange: (draft: string) => void;
  onSaveStateChange?: (saveState: SaveState) => void;
  onReviseSelection?: (selectedText: string) => void;
  onSendSelectionToChat?: (selectedText: string) => void;
}

export function DraftTab({
  activeSessionId,
  autoSaveEnabled = true,
  checkpointDisabled = false,
  checkpointPending = false,
  draft,
  onCreateCheckpoint,
  onDraftChange,
  onSaveStateChange,
  onReviseSelection,
  onSendSelectionToChat,
  serverDraft,
  taskId,
}: DraftTabProps) {
  const [mode, setMode] = useState<"preview" | "source">("preview");
  const [selectedText, setSelectedText] = useState("");
  const { lastSavedMarkdown, saveState } = useAutoSave(taskId, draft, autoSaveEnabled, serverDraft);
  useEffect(() => {
    onSaveStateChange?.(saveState);
  }, [onSaveStateChange, saveState]);
  const canCreateCheckpoint = Boolean(
    taskId
    && onCreateCheckpoint
    && !checkpointDisabled
    && !checkpointPending
    && saveState !== "saving",
  );

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
        <button
          className="primary-button"
          type="button"
          disabled={!canCreateCheckpoint}
          title={checkpointTitle({ checkpointDisabled, checkpointPending, hasTask: Boolean(taskId), saveState })}
          onClick={() => void onCreateCheckpoint?.(draft, lastSavedMarkdown)}
        >
          + Checkpoint
        </button>
        <span className="muted body-sm">last save · {saveState}</span>
      </div>
      <div className="draft-tab__body">
        {mode === "preview" ? (
          <LazyMarkdownPreview markdown={draft} />
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

function checkpointTitle({
  checkpointDisabled,
  checkpointPending,
  hasTask,
  saveState,
}: {
  checkpointDisabled: boolean;
  checkpointPending: boolean;
  hasTask: boolean;
  saveState: string;
}) {
  if (!hasTask) return "Create a workspace first";
  if (checkpointPending) return "Creating checkpoint";
  if (checkpointDisabled) return "Checkpoint is unavailable while the agent is running";
  if (saveState === "saving") return "Waiting for autosave to finish";
  return "Create a draft checkpoint";
}
