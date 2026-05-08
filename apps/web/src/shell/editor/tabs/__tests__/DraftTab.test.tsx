import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DraftTab } from "../DraftTab";

vi.mock("../../LazyDraftEditor", () => ({
  LazyDraftEditor: ({ onSelection }: { onSelection: (t: string) => void }) => (
    <div data-testid="editor" onClick={() => onSelection("selected text")} />
  ),
}));
vi.mock("../../MarkdownPreview", () => ({
  MarkdownPreview: () => <div data-testid="preview" />,
}));
vi.mock("../../../../api", () => ({
  api: { updateDraft: vi.fn().mockResolvedValue({ markdown: "" }) },
}));

describe("DraftTab selection bar", () => {
  it("hides selection bar when selection handlers are not provided", () => {
    render(
      <DraftTab
        activeSessionId="session-1"
        draft=""
        taskId="task-1"
        onDraftChange={() => undefined}
      />
    );
    fireEvent.click(screen.getByText("Source"));
    fireEvent.click(screen.getByTestId("editor"));

    expect(screen.queryByText("Send to chat")).toBeNull();
    expect(screen.queryByText("Revise selection")).toBeNull();
  });

  it("shows selection bar when selection handlers are provided", () => {
    render(
      <DraftTab
        activeSessionId="session-1"
        draft=""
        taskId="task-1"
        onDraftChange={() => undefined}
        onReviseSelection={vi.fn()}
        onSendSelectionToChat={vi.fn()}
      />
    );
    fireEvent.click(screen.getByText("Source"));
    fireEvent.click(screen.getByTestId("editor"));

    expect(screen.getByText("Send to chat")).toBeTruthy();
    expect(screen.getByText("Revise selection")).toBeTruthy();
  });
});
