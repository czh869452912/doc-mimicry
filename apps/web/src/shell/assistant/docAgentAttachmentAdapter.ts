import type { AttachmentAdapter, CompleteAttachment, PendingAttachment } from "@assistant-ui/react";
import { api } from "../../api";
import type { MessageAttachment } from "../../types";

interface DocAgentTextAttachmentAdapterOptions {
  onImported?: (reference: MessageAttachment) => void;
  taskId: string | null;
}

interface DocAgentPendingAttachment extends PendingAttachment {
  text: string;
}

const TEXT_ATTACHMENT_ACCEPT = [
  ".txt",
  ".md",
  ".markdown",
  ".csv",
  ".json",
  ".xml",
  ".html",
  ".css",
  "text/plain",
  "text/markdown",
  "text/csv",
  "text/html",
  "text/css",
  "application/json",
  "application/xml",
].join(",");

export function createDocAgentTextAttachmentAdapter({
  onImported,
  taskId,
}: DocAgentTextAttachmentAdapterOptions): AttachmentAdapter {
  return {
    accept: TEXT_ATTACHMENT_ACCEPT,
    async add({ file }) {
      return {
        id: `${file.name}-${file.size}-${file.lastModified}`,
        type: "document",
        name: file.name,
        contentType: file.type,
        file,
        text: await file.text(),
        status: { type: "requires-action", reason: "composer-send" },
      } satisfies DocAgentPendingAttachment;
    },
    async send(attachment) {
      if (!taskId) throw new Error("Create a workspace before attaching files.");
      const text = "text" in attachment && typeof attachment.text === "string"
        ? attachment.text
        : await attachment.file.text();
      const imported = await api.importTextInput(taskId, attachment.name, text);
      onImported?.({
        name: attachment.name,
        markdown_path: imported.markdown_path,
        source_path: imported.source_path,
        conversion_report_path: imported.conversion_report_path,
      });

      return {
        ...attachment,
        status: { type: "complete" },
        content: [
          {
            type: "text",
            text: `Imported attachment ${attachment.name} as ${imported.markdown_path}.`,
          },
        ],
      } satisfies CompleteAttachment;
    },
    async remove() {
      // The imported workspace file remains as context once a send has completed.
    },
  };
}
