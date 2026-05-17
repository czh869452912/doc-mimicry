import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { api } from "../../../api";
import { AcpComposer } from "../AcpComposer";

vi.mock("../../../api", () => ({
  api: {
    importFileInput: vi.fn(),
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

  it("uploads file attachments before sending", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn().mockResolvedValue(undefined);
    vi.mocked(api.importFileInput).mockResolvedValue({
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

    await waitFor(() => expect(api.importFileInput).toHaveBeenCalledWith("task-1", expect.any(File)));
    expect(onSend).toHaveBeenCalledWith("Use notes", [
      {
        name: "scope-notes.md",
        markdown_path: "inputs/markdown/scope-notes.md",
        source_path: "inputs/original/scope-notes.txt",
        conversion_report_path: "inputs/reports/scope-notes.json",
      },
    ]);
  });

  it("notifies the ACP surface attachment port after importing context files", async () => {
    const user = userEvent.setup();
    const onAttachContext = vi.fn().mockResolvedValue(undefined);
    vi.mocked(api.importFileInput).mockResolvedValue({
      id: "input-1",
      status: "converted",
      source_path: "inputs/original/context.txt",
      markdown_path: "inputs/markdown/context.md",
      conversion_report_path: "inputs/reports/context.json",
      original_filename: "context.txt",
      created_at: "2026-05-15T00:00:00Z",
    });
    render(
      <AcpComposer
        disabled={false}
        isRunning={false}
        taskId="task-1"
        onAttachContext={onAttachContext}
        onCancel={vi.fn()}
        onSend={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    await user.upload(
      document.querySelector('input[type="file"]') as HTMLInputElement,
      new File(["Attachment context"], "context.txt", { type: "text/plain" }),
    );
    await user.type(screen.getByLabelText("Message"), "Use context");
    await user.click(screen.getByRole("button", { name: /send message/i }));

    await waitFor(() => expect(onAttachContext).toHaveBeenCalledWith([
      {
        name: "context.txt",
        markdown_path: "inputs/markdown/context.md",
        source_path: "inputs/original/context.txt",
        conversion_report_path: "inputs/reports/context.json",
      },
    ]));
  });

  it("does not send failed binary conversions as message attachments", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn().mockResolvedValue(undefined);
    vi.mocked(api.importFileInput).mockResolvedValue({
      id: "input-deck",
      status: "failed",
      source_path: "inputs/original/deck.pptx",
      markdown_path: null,
      conversion_report_path: "inputs/reports/deck.conversion.json",
      original_filename: "deck.pptx",
      created_at: "2026-05-17T00:00:00Z",
      warnings: [{ type: "unsupported_format", message: "Unsupported import format: .pptx.", location: null }],
    });
    render(<AcpComposer disabled={false} isRunning={false} taskId="task-1" onCancel={vi.fn()} onSend={onSend} />);

    await user.upload(
      document.querySelector('input[type="file"]') as HTMLInputElement,
      new File(["not a deck"], "deck.pptx", { type: "application/vnd.openxmlformats-officedocument.presentationml.presentation" }),
    );
    await user.type(screen.getByLabelText("Message"), "Use deck");
    await user.click(screen.getByRole("button", { name: /send message/i }));

    await waitFor(() => expect(api.importFileInput).toHaveBeenCalledWith("task-1", expect.any(File)));
    expect(await screen.findByText(/could not be converted/i)).toBeTruthy();
    expect(onSend).toHaveBeenCalledWith("Use deck", []);
  });

  it("shows upload errors when attachment import fails", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn().mockResolvedValue(undefined);
    vi.mocked(api.importFileInput).mockRejectedValue(new Error("503 Service Unavailable"));
    render(<AcpComposer disabled={false} isRunning={false} taskId="task-1" onCancel={vi.fn()} onSend={onSend} />);

    await user.upload(
      document.querySelector('input[type="file"]') as HTMLInputElement,
      new File(["context"], "context.pdf", { type: "application/pdf" }),
    );
    await user.type(screen.getByLabelText("Message"), "Use context");
    await user.click(screen.getByRole("button", { name: /send message/i }));

    expect(await screen.findByText(/503 Service Unavailable/i)).toBeTruthy();
    expect(onSend).not.toHaveBeenCalled();
  });
});
