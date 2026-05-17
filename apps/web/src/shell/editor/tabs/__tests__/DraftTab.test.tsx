import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../../../api";
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
  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

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

  it("creates a checkpoint with the current and last saved draft text", () => {
    const createCheckpoint = vi.fn();
    render(
      <DraftTab
        activeSessionId="session-1"
        draft="# Draft"
        taskId="task-1"
        onCreateCheckpoint={createCheckpoint}
        onDraftChange={() => undefined}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /\+ checkpoint/i }));

    expect(createCheckpoint).toHaveBeenCalledWith("# Draft", "# Draft");
  });

  it("disables checkpoint creation while autosave is saving", async () => {
    vi.useFakeTimers();
    const createCheckpoint = vi.fn();
    const { rerender } = render(
      <DraftTab
        activeSessionId="session-1"
        draft="# Draft"
        taskId="task-1"
        onCreateCheckpoint={createCheckpoint}
        onDraftChange={() => undefined}
      />,
    );

    rerender(
      <DraftTab
        activeSessionId="session-1"
        draft={"# Draft\n\nUnsaved"}
        taskId="task-1"
        onCreateCheckpoint={createCheckpoint}
        onDraftChange={() => undefined}
      />,
    );

    expect((screen.getByRole("button", { name: /\+ checkpoint/i }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText("last save · saving")).toBeTruthy();
    expect(createCheckpoint).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(800);
    });
    expect(api.updateDraft).toHaveBeenCalledWith("task-1", "# Draft\n\nUnsaved");
  });
});
