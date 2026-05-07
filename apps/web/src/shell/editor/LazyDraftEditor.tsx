import { lazy, Suspense } from "react";
import type { DraftEditorProps } from "./DraftEditor";

const DraftEditor = lazy(() => import("./DraftEditor").then((module) => ({ default: module.DraftEditor })));

export function LazyDraftEditor(props: DraftEditorProps) {
  return (
    <Suspense fallback={<p className="pane-note">Loading editor...</p>}>
      <DraftEditor {...props} />
    </Suspense>
  );
}
