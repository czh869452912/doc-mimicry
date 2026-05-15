import { useMemo } from "react";
import { SLASH_COMMANDS } from "../conversation/slashCommands";

interface DocAgentSlashCommandsProps {
  query: string;
  onSelect: (command: string) => void;
}

export function DocAgentSlashCommands({ onSelect, query }: DocAgentSlashCommandsProps) {
  const suggestions = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized.startsWith("/")) return [];
    return SLASH_COMMANDS.filter((item) => item.command.startsWith(normalized));
  }, [query]);

  if (suggestions.length === 0) return null;

  return (
    <div className="acp-slash-menu" role="listbox" aria-label="Slash commands">
      {suggestions.map((item) => (
        <button
          aria-label={`${item.command} ${item.description}`}
          className="acp-slash-menu__item"
          key={item.command}
          type="button"
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => onSelect(item.command)}
        >
          <code>{item.command}</code>
          <span>{item.description}</span>
        </button>
      ))}
    </div>
  );
}
