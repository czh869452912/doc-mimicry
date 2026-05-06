import { describe, expect, it } from "vitest";
import { DRAFT_TAB, closeTab, titleFromPath, upsertTab } from "../editor/useTabs";

describe("editor tabs", () => {
  it("keeps the draft tab pinned while opening another tab", () => {
    const tabs = upsertTab([DRAFT_TAB], {
      id: "file:draft/draft.md",
      kind: "file",
      title: "draft.md",
      path: "draft/draft.md",
      content: "# Draft",
    });

    expect(tabs[0]).toEqual(DRAFT_TAB);
    expect(tabs[1]?.id).toBe("file:draft/draft.md");
  });

  it("does not close the pinned draft tab", () => {
    expect(closeTab([DRAFT_TAB], "draft")).toEqual([DRAFT_TAB]);
  });

  it("extracts a readable title from a workspace path", () => {
    expect(titleFromPath("context/style_notes.md")).toBe("style_notes.md");
  });
});
