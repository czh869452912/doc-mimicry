import ReactDiffViewer, { DiffMethod } from "react-diff-viewer-continued";

interface DiffViewerProps {
  left: string;
  leftTitle: string;
  right: string;
  rightTitle: string;
}

export function DiffViewer({ left, leftTitle, right, rightTitle }: DiffViewerProps) {
  return (
    <div className="diff-viewer">
      <ReactDiffViewer
        oldValue={left}
        newValue={right}
        leftTitle={leftTitle}
        rightTitle={rightTitle}
        splitView={true}
        compareMethod={DiffMethod.WORDS}
        useDarkTheme={false}
        styles={{
          variables: {
            light: {
              diffViewerBackground: "var(--color-surface)",
              diffViewerColor: "var(--color-ink)",
              addedBackground: "#e6ffec",
              addedColor: "#1a472a",
              removedBackground: "#ffebe9",
              removedColor: "#67060c",
              wordAddedBackground: "#acf2bd",
              wordRemovedBackground: "#fdb8c0",
            },
          },
        }}
      />
    </div>
  );
}
