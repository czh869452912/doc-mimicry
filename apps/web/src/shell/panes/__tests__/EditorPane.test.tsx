import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { EditorPane } from "../EditorPane";
import type { EditorTab } from "../../editor/useTabs";

const tabs: EditorTab[] = [
  { id: "draft", title: "Draft", kind: "draft", pinned: true },
  { id: "file:notes.md", title: "notes.md", kind: "file", path: "notes.md", content: "Notes" },
];

function renderEditor(overrides: Partial<Parameters<typeof EditorPane>[0]> = {}) {
  return render(
    <EditorPane
      activeSessionId={null}
      activeTabId="draft"
      draft="Current draft"
      tabs={tabs}
      taskId="task-1"
      onCloseTab={vi.fn()}
      onDraftChange={vi.fn()}
      onTabChange={vi.fn()}
      {...overrides}
    />,
  );
}

describe("EditorPane tabs", () => {
  it("keeps tab triggers free of nested buttons", () => {
    renderEditor();

    const tabButtons = screen.getAllByRole("tab");

    for (const tabButton of tabButtons) {
      expect(tabButton.querySelector("button")).toBeNull();
    }
  });

  it("closes a file tab from a separate close control", async () => {
    const user = userEvent.setup();
    const onCloseTab = vi.fn();
    renderEditor({ onCloseTab });

    await user.click(screen.getByRole("button", { name: "Close notes.md" }));

    expect(onCloseTab).toHaveBeenCalledWith("file:notes.md");
  });
});
