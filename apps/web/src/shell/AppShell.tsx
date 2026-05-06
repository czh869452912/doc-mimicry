import { Group, Panel, Separator } from "react-resizable-panels";
import { useState } from "react";
import { api } from "../api";
import type { WorkspaceFileContent } from "../types";
import { TopBar } from "./TopBar";
import { titleFromPath, tabKindForPath, useTabs } from "./editor/useTabs";
import { EditorPane } from "./panes/EditorPane";
import { WorkspacePane } from "./panes/WorkspacePane";
import { useWorkspaces } from "./state/useWorkspaces";

export function AppShell() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const workspaces = useWorkspaces();
  const editorTabs = useTabs();
  const topBarStatus = workspaces.activeSession?.status?.startsWith("running")
    ? "running"
    : workspaces.activeSession?.status === "failed"
      ? "failed"
      : "idle";

  return (
    <main className="docagent-shell">
      <TopBar
        workspaceLabel={workspaces.activeTask?.brief ?? "No workspace"}
        sessionLabel={workspaces.activeSession ? `session ${workspaces.activeSession.id.slice(0, 8)}` : "no session"}
        status={topBarStatus}
        onOpenCommandPalette={() => setCommandOpen(true)}
        onOpenSettings={() => setSettingsOpen(true)}
      />
      <Group orientation="horizontal" className="docagent-shell__panels">
        <Panel defaultSize={20} minSize={12} collapsible>
          <aside className="shell-panel">
            <WorkspacePane
              activeSession={workspaces.activeSession}
              activeTask={workspaces.activeTask}
              docTypes={workspaces.docTypes}
              error={workspaces.error}
              loading={workspaces.loading}
              nodes={workspaces.treeData}
              onCreateWorkspace={async (docTypeId, brief) => {
                const { task } = await workspaces.createWorkspace(docTypeId, brief);
                await loadDraft(task.id);
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
        <Panel minSize={32}>
          <section className="shell-panel shell-panel--center">
            <div className="shell-panel__placeholder">Conversation</div>
          </section>
        </Panel>
        <Separator className="resize-handle" />
        <Panel defaultSize={32} minSize={18} collapsible>
          <aside className="shell-panel">
            <EditorPane
              activeSessionId={workspaces.activeSession?.id ?? null}
              activeTabId={editorTabs.activeTabId}
              draft={draft}
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
      {settingsOpen && <div hidden>settings-open</div>}
      {commandOpen && <div hidden>command-open</div>}
    </main>
  );

  async function loadDraft(taskId: string) {
    const response = await api.getDraft(taskId);
    setDraft(response.markdown);
  }

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
