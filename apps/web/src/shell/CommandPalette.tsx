import { SLASH_COMMANDS } from "./conversation/slashCommands";
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from "../components/ui/command";

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
        <CommandInput autoFocus placeholder="Run command..." />
        <CommandList>
          <CommandEmpty>No command found.</CommandEmpty>
          {SLASH_COMMANDS.map((item) => (
            <CommandItem
              key={item.command}
              value={`${item.command} ${item.description}`}
              onSelect={() => {
                onRunCommand(item.command);
                onClose();
              }}
            >
              <code>{item.command}</code>
              <span>{item.description}</span>
            </CommandItem>
          ))}
        </CommandList>
      </Command>
    </div>
  );
}
