import { lazy, Suspense } from "react";
import type { DiffTabProps } from "./DiffTab";

const DiffTab = lazy(() =>
  import("./DiffTab").then((module) => ({ default: module.DiffTab })),
);

export function LazyDiffTab(props: DiffTabProps) {
  return (
    <Suspense fallback={<p className="pane-note">Loading diff...</p>}>
      <DiffTab {...props} />
    </Suspense>
  );
}
