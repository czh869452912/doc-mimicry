import { api } from "../../api";
import type { SessionRecord, TaskRecord } from "../../types";

export interface SlashCommandContext {
  activeTask: TaskRecord | null;
  ensureSession: () => Promise<SessionRecord | null>;
  openArtifact: (path: string) => Promise<void>;
  openHelp: () => void;
  refreshTimeline: () => Promise<unknown>;
  refreshWorkspace: () => Promise<unknown>;
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

  const session = await context.ensureSession();
  if (!session || !context.activeTask) return { handled: true, message: "Create a workspace first." };

  if (command === "/start") {
    await api.startLoop(session.id);
    await context.refreshWorkspace();
    await context.refreshTimeline();
    return { handled: true, message: "Outline loop started." };
  }
  if (command === "/check") {
    await api.runChecklist(session.id);
    await context.refreshWorkspace();
    await context.refreshTimeline();
    return { handled: true, message: "Checklist run finished." };
  }
  if (command === "/export") {
    const result = await api.exportMarkdown(session.id);
    await context.refreshWorkspace();
    await context.refreshTimeline();
    const artifactPath = result.artifact_path ?? "artifacts/prd-draft.md";
    await context.openArtifact(artifactPath);
    return { handled: true, message: "Markdown artifact exported." };
  }

  return { handled: false };
}

export const SLASH_COMMANDS = [
  { command: "/start", description: "Start outline loop" },
  { command: "/check", description: "Run checklist" },
  { command: "/export", description: "Export Markdown artifact" },
  { command: "/checkpoint", description: "Show checkpoint endpoint status" },
  { command: "/files", description: "Use the workspace tree to open files" },
  { command: "/versions", description: "Use the workspace tree to open versions" },
  { command: "/diff", description: "Open a diff after selecting versions" },
  { command: "/help", description: "Show command help" },
];
