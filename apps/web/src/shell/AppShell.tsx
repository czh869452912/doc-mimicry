import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type { WorkspaceFileContent } from "../types";
import { CommandPalette } from "./CommandPalette";
import { SettingsDrawer } from "./SettingsDrawer";
import { TopBar } from "./TopBar";
import { titleFromPath, tabKindForPath, useTabs } from "./editor/useTabs";
import { EditorPane } from "./panes/EditorPane";
import { ConversationPane } from "./panes/ConversationPane";
import { WorkspacePane } from "./panes/WorkspacePane";
import { useCollapse } from "./state/useCollapse";
import { useTimeline } from "./state/useTimeline";
import { useActiveWorkspace } from "./state/useActiveWorkspace";
import { useWorkspaceTree } from "./state/useWorkspaceTree";
import { useDraft } from "./state/useDraft";
import { buildWorkspaceTreeData } from "./state/useWorkspaces";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "../components/ui/resizable";
import { ErrorBoundary } from "./ErrorBoundary";

export function AppShell() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [queuedComposerDraft, setQueuedComposerDraft] = useState<string | null>(null);
  const [queuedCommand, setQueuedCommand] = useState<string | null>(null);
  const [localDraft, setLocalDraft] = useState<string | null>(null);
  const [checkpointPending, setCheckpointPending] = useState(false);
  const queryClient = useQueryClient();

  const workspaces = useActiveWorkspace();
  const activeTaskId = workspaces.activeTask?.id ?? null;
  const workspaceTreeQuery = useWorkspaceTree(activeTaskId);
  const draftQuery = useDraft(activeTaskId);
  const editorTabs = useTabs();
  const collapse = useCollapse();
  const timeline = useTimeline(workspaces.activeSession?.id, activeTaskId);

  useEffect(() => {
    setLocalDraft(null);
  }, [activeTaskId]);

  const draftQueryTaskId = draftQuery.isSuccess ? activeTaskId : null;
  const draft = localDraft ?? (draftQueryTaskId === activeTaskId ? draftQuery.data?.markdown : undefined) ?? "";
  const draftTaskId = draftQueryTaskId;
  const panelLayout = {
    left: collapse.leftPanelSize,
    center: 100 - collapse.leftPanelSize - collapse.rightPanelSize,
    right: collapse.rightPanelSize,
  };

  const workspaceTreeTasks = workspaces.activeTask
    ? [workspaces.activeTask, ...workspaces.tasks.filter((task) => task.id !== workspaces.activeTask?.id)]
    : workspaces.tasks;
  const treeData = buildWorkspaceTreeData(
    workspaceTreeTasks,
    workspaces.activeTask ? { [workspaces.activeTask.id]: workspaces.sessions } : {},
    workspaces.activeTask && workspaceTreeQuery.data
      ? { [workspaces.activeTask.id]: workspaceTreeQuery.data }
      : {},
  );

  const topBarStatus = workspaces.activeSession?.status?.startsWith("running")
    ? "running"
    : workspaces.activeSession?.status === "failed"
      ? "failed"
      : workspaces.activeSession?.status === "await_outline_approval"
        ? "waiting"
        : "idle";
  const activeSessionIsRunning = Boolean(workspaces.activeSession?.status?.startsWith("running"));

  return (
    <main className="docagent-shell" onKeyDown={handleKeyDown}>
      <TopBar
        workspaceLabel={workspaces.activeTask?.title ?? workspaces.activeTask?.brief ?? "No workspace"}
        sessionLabel={workspaces.activeSession ? `session ${workspaces.activeSession.id.slice(0, 8)}` : "no session"}
        status={topBarStatus}
        onOpenCommandPalette={() => setCommandOpen(true)}
        onOpenSettings={() => setSettingsOpen(true)}
      />
      <ResizablePanelGroup
        orientation="horizontal"
        className="docagent-shell__panels"
        defaultLayout={panelLayout}
        onLayoutChanged={collapse.rememberLayout}
      >
        <ResizablePanel id="left" defaultSize={collapse.leftPanelSize} minSize={12} collapsedSize={4} collapsible>
          <aside className="shell-panel">
            <ErrorBoundary label="Workspace">
              <WorkspacePane
                activeSession={workspaces.activeSession}
                activeTask={workspaces.activeTask}
                docTypes={workspaces.docTypes}
                error={workspaces.error}
                loading={workspaces.loading}
                nodes={treeData}
                sessions={workspaces.sessions}
                onCreateWorkspace={async (docTypeId, brief) => {
                  await workspaces.createWorkspace(docTypeId, brief);
                }}
                onCreateSession={async () => {
                  await workspaces.createSessionForActiveTask();
                }}
                onOpenFile={(path) => {
                  void openWorkspaceFile(path);
                }}
                onSelectSession={(sessionId) => {
                  const session = workspaces.sessions.find((s) => s.id === sessionId);
                  if (session) workspaces.selectSession(session);
                }}
                onSelectTask={(taskId) => {
                  const task = workspaces.tasks.find((t) => t.id === taskId);
                  if (task) workspaces.selectTask(task);
                }}
              />
            </ErrorBoundary>
          </aside>
        </ResizablePanel>
        <ResizableHandle className="resize-handle" />
        <ResizablePanel id="center" minSize={32}>
          <section className="shell-panel shell-panel--center">
            <ErrorBoundary label="Conversation">
              <ConversationPane
                activeSession={workspaces.activeSession}
                activeTask={workspaces.activeTask}
                createCheckpoint={() => createManualCheckpoint(draft, null)}
                createSession={workspaces.createSessionForActiveTask}
                ensureSession={workspaces.ensureSession}
                events={timeline.events}
                error={timeline.error}
                loading={timeline.loading}
                onOpenPath={openWorkspaceFile}
                onQueuedComposerDraftHandled={() => setQueuedComposerDraft(null)}
                onQueuedCommandHandled={() => setQueuedCommand(null)}
                queuedComposerDraft={queuedComposerDraft}
                queuedCommand={queuedCommand}
                refreshTimeline={timeline.refreshTimeline}
                refreshSessions={async () => {
                  await queryClient.invalidateQueries({ queryKey: ["sessions", workspaces.activeTask?.id] });
                }}
                refreshWorkspace={async () => {
                  await queryClient.invalidateQueries({ queryKey: ["workspace", workspaces.activeTask?.id] });
                  await queryClient.invalidateQueries({ queryKey: ["draft", workspaces.activeTask?.id] });
                }}
              />
            </ErrorBoundary>
          </section>
        </ResizablePanel>
        <ResizableHandle className="resize-handle" />
        <ResizablePanel id="right" defaultSize={collapse.rightPanelSize} minSize={18} collapsedSize={4} collapsible>
          <aside className="shell-panel">
            <ErrorBoundary label="Editor">
              <EditorPane
                activeSessionId={workspaces.activeSession?.id ?? null}
                activeTabId={editorTabs.activeTabId}
                checkpointDisabled={activeSessionIsRunning}
                checkpointPending={checkpointPending}
                draft={draft}
                draftAutoSaveEnabled={draftTaskId === (workspaces.activeTask?.id ?? null) && !activeSessionIsRunning}
                serverDraft={draftQueryTaskId === activeTaskId ? draftQuery.data?.markdown : undefined}
                tabs={editorTabs.tabs}
                taskId={workspaces.activeTask?.id ?? null}
                onCloseTab={editorTabs.removeTab}
                onCreateCheckpoint={createManualCheckpoint}
                onDraftChange={setLocalDraft}
                onReviseSelection={reviseSelectedText}
                onSendSelectionToChat={(selectedText) => {
                  setQueuedComposerDraft(selectionPrompt(selectedText));
                }}
                onTabChange={editorTabs.setActiveTabId}
              />
            </ErrorBoundary>
          </aside>
        </ResizablePanel>
      </ResizablePanelGroup>
      <CommandPalette open={commandOpen} onClose={() => setCommandOpen(false)} onRunCommand={setQueuedCommand} />
      <SettingsDrawer
        docTypes={workspaces.docTypes}
        open={settingsOpen}
        runtimeLabel={import.meta.env.VITE_DOCAGENT_RUNTIME ?? "mock"}
        onOpenChange={setSettingsOpen}
      />
    </main>
  );

  function handleKeyDown(event: React.KeyboardEvent) {
    if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === "p") {
      event.preventDefault();
      setCommandOpen(true);
    }
  }

  async function openWorkspaceFile(path: string) {
    if (!workspaces.activeTask) return;
    const file = await api.getWorkspaceFile(workspaces.activeTask.id, path);
    editorTabs.openTab(tabFromWorkspaceFile(file));
  }

  async function reviseSelectedText(selectedText: string) {
    if (!workspaces.activeSession) return;
    await api.reviseSelection(
      workspaces.activeSession.id,
      selectedText,
      "Please revise the selected passage while preserving its meaning.",
    );
    // SSE will push workspace/draft invalidation when the worker completes
  }

  async function createManualCheckpoint(draftMarkdown: string, lastSavedMarkdown: string | null) {
    if (!activeTaskId || activeSessionIsRunning || checkpointPending) return;
    setCheckpointPending(true);
    try {
      if (lastSavedMarkdown === null || draftMarkdown !== lastSavedMarkdown) {
        const response = await api.updateDraft(activeTaskId, draftMarkdown);
        setLocalDraft(response.markdown);
      }
      await api.createDraftCheckpoint(activeTaskId, "Manual checkpoint");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["workspace", activeTaskId] }),
        workspaces.activeSession?.id ? timeline.refreshTimeline() : Promise.resolve(),
      ]);
    } finally {
      setCheckpointPending(false);
    }
  }
}

function selectionPrompt(selectedText: string) {
  return `Please review this selected passage and suggest improvements:\n\n> ${selectedText}`;
}

function tabFromWorkspaceFile(file: WorkspaceFileContent) {
  const kind = tabKindForPath(file.path);
  const common = { id: `${kind}:${file.path}`, title: titleFromPath(file.path), path: file.path, content: file.content };
  if (kind === "version") return { ...common, kind };
  if (kind === "artifact") return { ...common, kind };
  return { ...common, kind: "file" as const };
}
