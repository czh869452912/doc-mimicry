import { diffLines } from "diff";

interface DiffViewerProps {
  left: string;
  leftTitle: string;
  right: string;
  rightTitle: string;
}

export function DiffViewer({ left, leftTitle, right, rightTitle }: DiffViewerProps) {
  const parts = diffLines(left, right);

  return (
    <div className="diff-viewer">
      <header className="diff-viewer__header">
        <span>{leftTitle}</span>
        <span>{rightTitle}</span>
      </header>
      <div className="diff-viewer__body">
        <pre>
          {parts
            .filter((part) => !part.added)
            .map((part, index) => (
              <span key={`left-${index}`} className={part.removed ? "diff-line diff-line--removed" : "diff-line"}>
                {part.value}
              </span>
            ))}
        </pre>
        <pre>
          {parts
            .filter((part) => !part.removed)
            .map((part, index) => (
              <span key={`right-${index}`} className={part.added ? "diff-line diff-line--added" : "diff-line"}>
                {part.value}
              </span>
            ))}
        </pre>
      </div>
    </div>
  );
}
