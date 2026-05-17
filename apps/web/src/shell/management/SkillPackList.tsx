import { Badge } from "../../components/ui/badge";
import type { SkillPackSummary } from "../../types";

interface SkillPackListProps {
  loading: boolean;
  packs: SkillPackSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function SkillPackList({ loading, onSelect, packs, selectedId }: SkillPackListProps) {
  return (
    <div className="skill-pack-list" aria-label="Skill packs">
      {packs.map((pack) => (
        <button
          className={pack.id === selectedId ? "active" : ""}
          key={pack.id}
          type="button"
          onClick={() => onSelect(pack.id)}
        >
          <span>{pack.title}</span>
          <Badge variant={pack.latest_version_id ? "secondary" : "outline"}>
            {pack.latest_version_id ? "published" : pack.draft_status}
          </Badge>
        </button>
      ))}
      {!loading && packs.length === 0 ? <p className="muted">No skill packs yet.</p> : null}
    </div>
  );
}
