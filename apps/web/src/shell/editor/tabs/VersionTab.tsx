import { LazyDraftEditor } from "../LazyDraftEditor";

interface VersionTabProps {
  content: string;
}

export function VersionTab({ content }: VersionTabProps) {
  return <LazyDraftEditor markdown={content} readOnly />;
}
