import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../api";
import type { SessionRecord, TaskRecord } from "../../types";
import { executeSlashCommand, SLASH_COMMANDS, type SlashCommandContext } from "./slashCommands";

vi.mock("../../api", () => ({
  api: {
    createDraftCheckpoint: vi.fn(),
    exportDocx: vi.fn(),
    exportPdf: vi.fn(),
  },
}));

const task: TaskRecord = {
  id: "task-1",
  doc_type_id: "prd",
  brief: "Write a PRD",
  title: "PRD task",
  workspace_root: "workspace/task-1",
  created_at: "2026-05-06T08:00:00Z",
  updated_at: "2026-05-06T08:00:00Z",
};

const session: SessionRecord = {
  id: "session-1",
  task_id: "task-1",
  status: "draft_ready",
  created_at: "2026-05-06T08:00:00Z",
  updated_at: "2026-05-06T08:00:00Z",
};

function commandContext(overrides: Partial<SlashCommandContext> = {}): SlashCommandContext {
  return {
    activeSession: session,
    activeTask: task,
    createSession: vi.fn().mockResolvedValue(session),
    ensureSession: vi.fn().mockResolvedValue(session),
    openArtifact: vi.fn().mockResolvedValue(undefined),
    openHelp: vi.fn(),
    refreshTimeline: vi.fn().mockResolvedValue(undefined),
    refreshWorkspace: vi.fn().mockResolvedValue(undefined),
    refreshSessions: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

describe("slash commands", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("exports DOCX artifacts without using the Markdown export command", async () => {
    const context = commandContext();
    vi.mocked(api.exportDocx).mockResolvedValue({
      session_id: "session-1",
      artifact_path: "artifacts/prd-draft.docx",
    });

    const result = await executeSlashCommand("/export-docx", context);

    expect(result).toEqual({
      handled: true,
      message: "Exported DOCX artifact: artifacts/prd-draft.docx",
    });
    expect(api.exportDocx).toHaveBeenCalledWith("session-1");
    expect(context.refreshTimeline).toHaveBeenCalledOnce();
    expect(context.refreshWorkspace).toHaveBeenCalledOnce();
    expect(context.refreshSessions).toHaveBeenCalledOnce();
  });

  it("exports PDF artifacts through the product export boundary", async () => {
    const context = commandContext();
    vi.mocked(api.exportPdf).mockResolvedValue({
      session_id: "session-1",
      artifact_path: "artifacts/prd-draft.pdf",
    });

    const result = await executeSlashCommand("/export-pdf", context);

    expect(result).toEqual({
      handled: true,
      message: "Exported PDF artifact: artifacts/prd-draft.pdf",
    });
    expect(api.exportPdf).toHaveBeenCalledWith("session-1");
    expect(context.refreshTimeline).toHaveBeenCalledOnce();
    expect(context.refreshWorkspace).toHaveBeenCalledOnce();
  });

  it("runs checkpoint command through the provided authoring checkpoint action", async () => {
    const createCheckpoint = vi.fn().mockResolvedValue(undefined);
    const context = commandContext({ createCheckpoint });

    const result = await executeSlashCommand("/checkpoint", context);

    expect(result).toEqual({
      handled: true,
      message: "Checkpoint created.",
    });
    expect(createCheckpoint).toHaveBeenCalledOnce();
  });

  it("lists DOCX and PDF export commands", () => {
    expect(SLASH_COMMANDS.map((item) => item.command)).toContain("/export-docx");
    expect(SLASH_COMMANDS.map((item) => item.command)).toContain("/export-pdf");
  });
});
