import { Group, Panel, Separator } from "react-resizable-panels";
import { useState } from "react";
import { TopBar } from "./TopBar";
import { WorkspacePane } from "./panes/WorkspacePane";
import { useWorkspaces } from "./state/useWorkspaces";

export function AppShell() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const workspaces = useWorkspaces();
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
                await workspaces.createWorkspace(docTypeId, brief);
              }}
              onOpenFile={() => undefined}
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
            <div className="shell-panel__placeholder">Draft</div>
          </aside>
        </Panel>
      </Group>
      {settingsOpen && <div hidden>settings-open</div>}
      {commandOpen && <div hidden>command-open</div>}
    </main>
  );
}
