import { lazy, Suspense } from "react";
import type { MarkdownPreviewProps } from "./MarkdownPreview";

const MarkdownPreview = lazy(() =>
  import("./MarkdownPreview").then((module) => ({ default: module.MarkdownPreview })),
);

export function LazyMarkdownPreview(props: MarkdownPreviewProps) {
  return (
    <Suspense fallback={<div className="markdown-preview body-md">Loading preview...</div>}>
      <MarkdownPreview {...props} />
    </Suspense>
  );
}
