import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { api } from "../../../api";
import { AcpComposer } from "../AcpComposer";

vi.mock("../../../api", () => ({
  api: {
    importTextInput: vi.fn(),
  },
}));

describe("AcpComposer", () => {
  it("sends text input on click", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn().mockResolvedValue(undefined);
    render(<AcpComposer disabled={false} isRunning={false} onCancel={vi.fn()} onSend={onSend} />);

    await user.type(screen.getByLabelText("Message"), "Draft this");
    await user.click(screen.getByRole("button", { name: /send message/i }));

    expect(onSend).toHaveBeenCalledWith("Draft this", []);
  });

  it("applies queued draft text and notifies caller", () => {
    const onDraftTextApplied = vi.fn();
    render(
      <AcpComposer
        disabled={false}
        draftText="Revise selection"
        isRunning={false}
        onCancel={vi.fn()}
        onDraftTextApplied={onDraftTextApplied}
        onSend={vi.fn()}
      />,
    );

    expect((screen.getByLabelText("Message") as HTMLTextAreaElement).value).toBe("Revise selection");
    expect(onDraftTextApplied).toHaveBeenCalled();
  });

  it("calls cancel when running", async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    render(<AcpComposer disabled={false} isRunning onCancel={onCancel} onSend={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: /stop the running agent/i }));
    expect(onCancel).toHaveBeenCalled();
  });

  it("imports text attachments before sending", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn().mockResolvedValue(undefined);
    vi.mocked(api.importTextInput).mockResolvedValue({
      id: "input-1",
      status: "converted",
      source_path: "inputs/original/scope-notes.txt",
      markdown_path: "inputs/markdown/scope-notes.md",
      conversion_report_path: "inputs/reports/scope-notes.json",
      original_filename: "scope-notes.md",
      created_at: "2026-05-15T00:00:00Z",
    });
    render(<AcpComposer disabled={false} isRunning={false} taskId="task-1" onCancel={vi.fn()} onSend={onSend} />);

    await user.upload(
      document.querySelector('input[type="file"]') as HTMLInputElement,
      new File(["Attachment context"], "scope-notes.md", { type: "text/markdown" }),
    );
    expect(await screen.findByText("scope-notes.md")).toBeTruthy();

    await user.type(screen.getByLabelText("Message"), "Use notes");
    await user.click(screen.getByRole("button", { name: /send message/i }));

    await waitFor(() => expect(api.importTextInput).toHaveBeenCalledWith("task-1", "scope-notes.md", "Attachment context"));
    expect(onSend).toHaveBeenCalledWith("Use notes", [
      {
        name: "scope-notes.md",
        markdown_path: "inputs/markdown/scope-notes.md",
        source_path: "inputs/original/scope-notes.txt",
        conversion_report_path: "inputs/reports/scope-notes.json",
      },
    ]);
  });
});
