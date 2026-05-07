import { useEffect, useRef, useState } from "react";
import { api } from "../../api";

export type SaveState = "idle" | "saving" | "saved" | "error";

export function useAutoSave(taskId: string | null | undefined, markdown: string, enabled = true) {
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const lastSaved = useRef(markdown);

  useEffect(() => {
    if (!enabled) return;
    lastSaved.current = markdown;
    setSaveState("idle");
  }, [enabled, taskId]);

  useEffect(() => {
    if (!enabled || !taskId || markdown === lastSaved.current) return;
    setSaveState("saving");
    const timer = window.setTimeout(() => {
      api
        .updateDraft(taskId, markdown)
        .then((response) => {
          lastSaved.current = response.markdown;
          setSaveState("saved");
        })
        .catch(() => {
          setSaveState("error");
        });
    }, 800);

    return () => window.clearTimeout(timer);
  }, [enabled, markdown, taskId]);

  return saveState;
}
