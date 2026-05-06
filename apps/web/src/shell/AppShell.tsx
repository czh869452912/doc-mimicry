import { Group, Panel, Separator } from "react-resizable-panels";
import { useState } from "react";
import { TopBar } from "./TopBar";

export function AppShell() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);

  return (
    <main className="docagent-shell">
      <TopBar
        workspaceLabel="No workspace"
        sessionLabel="no session"
        status="idle"
        onOpenCommandPalette={() => setCommandOpen(true)}
        onOpenSettings={() => setSettingsOpen(true)}
      />
      <Group orientation="horizontal" className="docagent-shell__panels">
        <Panel defaultSize={20} minSize={12} collapsible>
          <aside className="shell-panel">
            <div className="shell-panel__placeholder">Workspace</div>
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
