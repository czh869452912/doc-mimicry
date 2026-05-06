import { Command } from "cmdk";
import { SLASH_COMMANDS } from "./conversation/slashCommands";

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  onRunCommand: (command: string) => void;
}

export function CommandPalette({ onClose, onRunCommand, open }: CommandPaletteProps) {
  if (!open) return null;

  return (
    <div className="command-overlay" role="presentation" onMouseDown={onClose}>
      <Command
        className="command-menu"
        label="Command palette"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <Command.Input autoFocus placeholder="Run command..." />
        <Command.List>
          <Command.Empty>No command found.</Command.Empty>
          {SLASH_COMMANDS.map((item) => (
            <Command.Item
              key={item.command}
              value={`${item.command} ${item.description}`}
              onSelect={() => {
                onRunCommand(item.command);
                onClose();
              }}
            >
              <code>{item.command}</code>
              <span>{item.description}</span>
            </Command.Item>
          ))}
        </Command.List>
      </Command>
    </div>
  );
}
