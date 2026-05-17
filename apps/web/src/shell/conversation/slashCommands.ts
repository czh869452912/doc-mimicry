import { api } from "../../api";
import type { SessionRecord, TaskRecord } from "../../types";

export interface SlashCommandContext {
  activeSession: SessionRecord | null;
  activeTask: TaskRecord | null;
  createSession: () => Promise<SessionRecord | null>;
  ensureSession: () => Promise<SessionRecord | null>;
  openArtifact: (path: string) => Promise<void>;
  openHelp: () => void;
  refreshTimeline: () => Promise<unknown>;
  refreshWorkspace: () => Promise<unknown>;
  refreshSessions?: () => Promise<unknown>;
}

export interface SlashCommandResult {
  handled: boolean;
  message?: string;
}

export async function executeSlashCommand(input: string, context: SlashCommandContext): Promise<SlashCommandResult> {
  const [command, ...args] = input.trim().split(/\s+/);
  if (!command?.startsWith("/")) return { handled: false };

  if (command === "/help") {
    context.openHelp();
    return { handled: true, message: "Opened help" };
  }
  if (command === "/checkpoint") {
    return { handled: true, message: "Checkpoint endpoint is not available yet." };
  }
  if (command === "/files" || command === "/versions") {
    return { handled: true, message: `${command.slice(1)} view is available from the workspace tree.` };
  }
  if (command === "/diff") {
    return { handled: true, message: `/diff ${args.join(" ")} will open after version tabs are selected.` };
  }

  if (command === "/start") {
    const session = context.activeSession?.status === "idle" ? context.activeSession : await context.createSession();
    if (!session || !context.activeTask) return { handled: true, message: "Create a workspace first." };
    await api.startLoop(session.id);
    await Promise.all([context.refreshTimeline(), context.refreshWorkspace(), context.refreshSessions?.()]);
    return { handled: true, message: "Outline loop starting…" };
  }

  const session = await context.ensureSession();
  if (!session || !context.activeTask) return { handled: true, message: "Create a workspace first." };

  if (command === "/check") {
    await api.runChecklist(session.id);
    await Promise.all([context.refreshTimeline(), context.refreshWorkspace(), context.refreshSessions?.()]);
    return { handled: true, message: "Checklist running…" };
  }
  if (command === "/export") {
    await api.exportMarkdown(session.id);
    await Promise.all([context.refreshTimeline(), context.refreshWorkspace(), context.refreshSessions?.()]);
    return { handled: true, message: "Export started. Open the artifact from the workspace tree when it appears." };
  }
  if (command === "/export-docx") {
    const result = await api.exportDocx(session.id);
    await Promise.all([context.refreshTimeline(), context.refreshWorkspace(), context.refreshSessions?.()]);
    const path = result.artifact_path ?? "workspace artifacts";
    return { handled: true, message: `Exported DOCX artifact: ${path}` };
  }
  if (command === "/export-pdf") {
    const result = await api.exportPdf(session.id);
    await Promise.all([context.refreshTimeline(), context.refreshWorkspace(), context.refreshSessions?.()]);
    const path = result.artifact_path ?? "workspace artifacts";
    return { handled: true, message: `Exported PDF artifact: ${path}` };
  }

  return { handled: false };
}

export const SLASH_COMMANDS = [
  { command: "/start", description: "Start outline loop" },
  { command: "/check", description: "Run checklist" },
  { command: "/export", description: "Export Markdown artifact" },
  { command: "/export-docx", description: "Export DOCX artifact" },
  { command: "/export-pdf", description: "Export PDF artifact" },
  { command: "/checkpoint", description: "Show checkpoint endpoint status" },
  { command: "/files", description: "Use the workspace tree to open files" },
  { command: "/versions", description: "Use the workspace tree to open versions" },
  { command: "/diff", description: "Open a diff after selecting versions" },
  { command: "/help", description: "Show command help" },
];
