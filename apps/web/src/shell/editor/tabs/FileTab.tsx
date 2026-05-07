import { LazyDraftEditor } from "../LazyDraftEditor";
import { MarkdownPreview } from "../MarkdownPreview";

interface FileTabProps {
  content: string;
  path: string;
}

export function FileTab({ content, path }: FileTabProps) {
  return path.endsWith(".md") ? (
    <MarkdownPreview markdown={content} />
  ) : (
    <LazyDraftEditor markdown={content} readOnly />
  );
}
