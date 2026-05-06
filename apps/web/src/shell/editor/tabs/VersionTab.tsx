import { DraftEditor } from "../DraftEditor";

interface VersionTabProps {
  content: string;
}

export function VersionTab({ content }: VersionTabProps) {
  return <DraftEditor markdown={content} readOnly />;
}
