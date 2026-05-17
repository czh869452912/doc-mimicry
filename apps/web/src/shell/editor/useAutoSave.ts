import { useEffect, useRef, useState } from "react";
import { api } from "../../api";

export type SaveState = "idle" | "saving" | "saved" | "error";

export interface AutoSaveSnapshot {
  lastSavedMarkdown: string;
  saveState: SaveState;
}

export function useAutoSave(
  taskId: string | null | undefined,
  markdown: string,
  enabled = true,
  serverMarkdown?: string,
): AutoSaveSnapshot {
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [lastSavedMarkdown, setLastSavedMarkdown] = useState(markdown);
  const lastSaved = useRef(markdown);

  useEffect(() => {
    const snapshot = serverMarkdown ?? markdown;
    lastSaved.current = snapshot;
    setLastSavedMarkdown(snapshot);
    setSaveState("idle");
  }, [serverMarkdown, taskId]);

  useEffect(() => {
    if (!enabled || !taskId || markdown === lastSaved.current) return;
    setSaveState("saving");
    const timer = window.setTimeout(() => {
      api
        .updateDraft(taskId, markdown)
        .then((response) => {
          lastSaved.current = response.markdown;
          setLastSavedMarkdown(response.markdown);
          setSaveState("saved");
        })
        .catch(() => {
          setSaveState("error");
        });
    }, 800);

    return () => window.clearTimeout(timer);
  }, [enabled, markdown, taskId]);

  return { lastSavedMarkdown, saveState };
}
