import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
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
import { useWorkspaces } from "./state/useWorkspaces";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "../components/ui/resizable";
import { ErrorBoundary } from "./ErrorBoundary";

export function AppShell() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialTaskId = useRef(searchParams.get("task")).current;
  const initialSessionId = useRef(searchParams.get("session")).current;
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [draftTaskId, setDraftTaskId] = useState<string | null>(null);
  const [draftReloadToken, setDraftReloadToken] = useState(0);
  const [queuedComposerDraft, setQueuedComposerDraft] = useState<string | null>(null);
  const [queuedCommand, setQueuedCommand] = useState<string | null>(null);
  const workspaces = useWorkspaces(initialTaskId, initialSessionId);
  const editorTabs = useTabs();
  const collapse = useCollapse();
  const timeline = useTimeline(workspaces.activeSession?.id, workspaces.activeTask?.id);
  const topBarStatus = workspaces.activeSession?.status?.startsWith("running")
    ? "running"
    : workspaces.activeSession?.status === "failed"
      ? "failed"
      : "idle";

  useEffect(() => {
    let cancelled = false;
    const taskId = workspaces.activeTask?.id;

    if (!taskId) {
      setDraft("");
      setDraftTaskId(null);
      return;
    }
    const activeTaskId = taskId;
    setDraft("");
    setDraftTaskId(null);

    async function loadActiveDraft() {
      try {
        const response = await api.getDraft(activeTaskId);
        if (!cancelled) {
          setDraft(response.markdown);
          setDraftTaskId(activeTaskId);
        }
      } catch {
        if (!cancelled) {
          setDraft("");
          setDraftTaskId(activeTaskId);
        }
      }
    }

    void loadActiveDraft();
    return () => {
      cancelled = true;
    };
  }, [draftReloadToken, workspaces.activeTask?.id]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandOpen(true);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (workspaces.loading) return;
    const params: Record<string, string> = {};
    if (workspaces.activeTask) params.task = workspaces.activeTask.id;
    if (workspaces.activeSession) params.session = workspaces.activeSession.id;
    setSearchParams(params, { replace: true });
  }, [workspaces.loading, workspaces.activeTask?.id, workspaces.activeSession?.id, setSearchParams]);

  useEffect(() => {
    if (!workspaces.activeSession?.status?.startsWith("running")) return;
    let cancelled = false;
    const intervalId = window.setInterval(() => {
      void workspaces.refreshActiveWorkspace().then(() => {
        if (!cancelled) setDraftReloadToken((token) => token + 1);
      });
    }, 1500);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [workspaces.activeSession?.id, workspaces.activeSession?.status, workspaces.refreshActiveWorkspace]);

  return (
    <main className="docagent-shell">
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
        defaultLayout={{ left: collapse.leftPanelSize, center: 100 - collapse.leftPanelSize - collapse.rightPanelSize, right: collapse.rightPanelSize }}
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
              nodes={workspaces.treeData}
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
                const session = workspaces.sessions.find((item) => item.id === sessionId);
                if (session) void workspaces.selectSession(session);
              }}
              onSelectTask={(taskId) => {
                const task = workspaces.tasks.find((item) => item.id === taskId);
                if (task) void workspaces.selectTask(task);
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
              refreshWorkspace={async () => {
                await workspaces.refreshActiveWorkspace();
                setDraftReloadToken((token) => token + 1);
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
              draft={draft}
              draftAutoSaveEnabled={draftTaskId === (workspaces.activeTask?.id ?? null)}
              tabs={editorTabs.tabs}
              taskId={workspaces.activeTask?.id ?? null}
              onCloseTab={editorTabs.removeTab}
              onDraftChange={setDraft}
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
    await timeline.refreshTimeline();
    await workspaces.refreshActiveWorkspace();
    setDraftReloadToken((token) => token + 1);
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
