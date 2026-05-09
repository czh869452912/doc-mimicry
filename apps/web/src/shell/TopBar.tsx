import { Settings } from "lucide-react";

interface TopBarProps {
  workspaceLabel: string;
  sessionLabel: string;
  status: "idle" | "running" | "failed" | "waiting";
  onOpenCommandPalette: () => void;
  onOpenSettings: () => void;
}

export function TopBar({
  workspaceLabel,
  sessionLabel,
  status,
  onOpenCommandPalette,
  onOpenSettings,
}: TopBarProps) {
  return (
    <header className="topbar">
      <strong className="topbar__brand title-sm">DocAgent</strong>
      <span className="topbar__crumb body-sm">· {workspaceLabel}</span>
      <span className="topbar__session body-sm">/ {sessionLabel}</span>
      <span className="status-dot" data-status={status} aria-label={`Session status: ${status}`} />
      <span className="topbar__spacer" />
      <button className="command-chip" type="button" onClick={onOpenCommandPalette}>
        Ctrl K
      </button>
      <button className="icon-button" type="button" aria-label="Open settings" onClick={onOpenSettings}>
        <Settings size={15} />
      </button>
    </header>
  );
}
