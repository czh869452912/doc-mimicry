import { MarkdownPreview } from "../MarkdownPreview";

interface ArtifactTabProps {
  content: string;
  path: string;
}

export function ArtifactTab({ content, path }: ArtifactTabProps) {
  return (
    <section className="artifact-tab">
      <div className="editor-toolbar">
        <span className="code-text muted">{path}</span>
        <button type="button" disabled title="Reveal in folder is not available in the browser yet">
          Reveal in folder
        </button>
      </div>
      <MarkdownPreview markdown={content} />
    </section>
  );
}
