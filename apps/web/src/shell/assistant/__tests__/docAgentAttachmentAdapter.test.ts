import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../../api";
import { createDocAgentTextAttachmentAdapter } from "../docAgentAttachmentAdapter";
import type { PendingAttachment } from "@assistant-ui/react";

vi.mock("../../../api", () => ({
  api: {
    importTextInput: vi.fn(),
  },
}));

describe("createDocAgentTextAttachmentAdapter", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("imports text attachments into workspace inputs when sent", async () => {
    vi.mocked(api.importTextInput).mockResolvedValue({
      id: "input-source-notes",
      status: "converted",
      source_path: "inputs/original/source-notes.txt",
      markdown_path: "inputs/markdown/source-notes.md",
      conversion_report_path: "inputs/reports/source-notes.json",
      original_filename: "source-notes.md",
      created_at: "2026-05-08T00:00:00Z",
    });
    const adapter = createDocAgentTextAttachmentAdapter({ taskId: "task-1" });
    const file = new File(["Launch scope notes"], "source-notes.md", { type: "text/markdown" });

    const pending = await addAttachment(adapter.add({ file }));
    const complete = await adapter.send(pending);

    expect(api.importTextInput).toHaveBeenCalledWith("task-1", "source-notes.md", "Launch scope notes");
    expect(complete.status).toEqual({ type: "complete" });
    expect(complete.content).toEqual([
      {
        type: "text",
        text: "Imported attachment source-notes.md as inputs/markdown/source-notes.md.",
      },
    ]);
  });

  it("refuses to send when no active task is available", async () => {
    const adapter = createDocAgentTextAttachmentAdapter({ taskId: null });
    const file = new File(["No workspace"], "notes.txt", { type: "text/plain" });

    const pending = await addAttachment(adapter.add({ file }));

    await expect(adapter.send(pending)).rejects.toThrow("Create a workspace before attaching files.");
    expect(api.importTextInput).not.toHaveBeenCalled();
  });
});

async function addAttachment(
  result: Promise<PendingAttachment> | AsyncGenerator<PendingAttachment, void>,
) {
  if (Symbol.asyncIterator in result) {
    let latest: PendingAttachment | null = null;
    for await (const attachment of result) latest = attachment;
    if (!latest) throw new Error("Attachment adapter did not yield an attachment.");
    return latest;
  }
  return result;
}
