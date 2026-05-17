import { LazyDraftEditor } from "../LazyDraftEditor";
import { LazyMarkdownPreview } from "../LazyMarkdownPreview";

interface FileTabProps {
  content: string;
  path: string;
}

export function FileTab({ content, path }: FileTabProps) {
  return path.endsWith(".md") ? (
    <LazyMarkdownPreview markdown={content} />
  ) : (
    <LazyDraftEditor markdown={content} readOnly />
  );
}
