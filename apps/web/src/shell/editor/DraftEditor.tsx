import { markdown } from "@codemirror/lang-markdown";
import { EditorView } from "@codemirror/view";
import CodeMirror from "@uiw/react-codemirror";
import { useMemo } from "react";

export interface DraftEditorProps {
  markdown: string;
  readOnly?: boolean;
  onChange?: (markdown: string) => void;
  onSelection?: (selectedText: string) => void;
}

export function DraftEditor({ markdown: value, onChange, onSelection, readOnly = false }: DraftEditorProps) {
  const selectionListener = useMemo(
    () =>
      EditorView.updateListener.of((viewUpdate) => {
        if (!viewUpdate.selectionSet) return;
        const selection = viewUpdate.state.sliceDoc(
          viewUpdate.state.selection.main.from,
          viewUpdate.state.selection.main.to,
        );
        onSelection?.(selection);
      }),
    [onSelection],
  );

  const extensions = useMemo(
    () => [markdown(), EditorView.lineWrapping, selectionListener],
    [selectionListener],
  );

  return (
    <CodeMirror
      basicSetup
      className="draft-source-editor"
      editable={!readOnly}
      extensions={extensions}
      height="100%"
      theme="light"
      value={value}
      onChange={(nextValue, viewUpdate) => {
        onChange?.(nextValue);
        const selection = viewUpdate.state.sliceDoc(
          viewUpdate.state.selection.main.from,
          viewUpdate.state.selection.main.to,
        );
        onSelection?.(selection);
      }}
    />
  );
}
