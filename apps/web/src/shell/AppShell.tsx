import { Group, Panel, Separator } from "react-resizable-panels";
import { useEffect, useState } from "react";
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

export function AppShell() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [draftTaskId, setDraftTaskId] = useState<string | null>(null);
  const [draftReloadToken, setDraftReloadToken] = useState(0);
  const [queuedCommand, setQueuedCommand] = useState<string | null>(null);
  const workspaces = useWorkspaces();
  const editorTabs = useTabs();
  const collapse = useCollapse();
  const timeline = useTimeline(workspaces.activeSession?.id);
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

  return (
    <main className="docagent-shell">
      <TopBar
        workspaceLabel={workspaces.activeTask?.title ?? workspaces.activeTask?.brief ?? "No workspace"}
        sessionLabel={workspaces.activeSession ? `session ${workspaces.activeSession.id.slice(0, 8)}` : "no session"}
        status={topBarStatus}
        onOpenCommandPalette={() => setCommandOpen(true)}
        onOpenSettings={() => setSettingsOpen(true)}
      />
      <Group
        orientation="horizontal"
        className="docagent-shell__panels"
        defaultLayout={{ left: collapse.leftPanelSize, center: 100 - collapse.leftPanelSize - collapse.rightPanelSize, right: collapse.rightPanelSize }}
        onLayoutChanged={collapse.rememberLayout}
      >
        <Panel id="left" defaultSize={collapse.leftPanelSize} minSize={12} collapsedSize={4} collapsible>
          <aside className="shell-panel">
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
          </aside>
        </Panel>
        <Separator className="resize-handle" />
        <Panel id="center" minSize={32}>
          <section className="shell-panel shell-panel--center">
            <ConversationPane
              activeSession={workspaces.activeSession}
              activeTask={workspaces.activeTask}
              ensureSession={workspaces.ensureSession}
              error={timeline.error}
              loading={timeline.loading}
              onOpenPath={openWorkspaceFile}
              onQueuedCommandHandled={() => setQueuedCommand(null)}
              presentations={timeline.presentations}
              queuedCommand={queuedCommand}
              refreshTimeline={timeline.refreshTimeline}
              refreshWorkspace={async () => {
                await workspaces.refreshActiveWorkspace();
                setDraftReloadToken((token) => token + 1);
              }}
            />
          </section>
        </Panel>
        <Separator className="resize-handle" />
        <Panel id="right" defaultSize={collapse.rightPanelSize} minSize={18} collapsedSize={4} collapsible>
          <aside className="shell-panel">
            <EditorPane
              activeSessionId={workspaces.activeSession?.id ?? null}
              activeTabId={editorTabs.activeTabId}
              draft={draft}
              draftAutoSaveEnabled={draftTaskId === (workspaces.activeTask?.id ?? null)}
              tabs={editorTabs.tabs}
              taskId={workspaces.activeTask?.id ?? null}
              onCloseTab={editorTabs.removeTab}
              onDraftChange={setDraft}
              onReviseSelection={() => undefined}
              onSendSelectionToChat={() => undefined}
              onTabChange={editorTabs.setActiveTabId}
            />
          </aside>
        </Panel>
      </Group>
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
}

function tabFromWorkspaceFile(file: WorkspaceFileContent) {
  const kind = tabKindForPath(file.path);
  const common = { id: `${kind}:${file.path}`, title: titleFromPath(file.path), path: file.path, content: file.content };
  if (kind === "version") return { ...common, kind };
  if (kind === "artifact") return { ...common, kind };
  return { ...common, kind: "file" as const };
}
