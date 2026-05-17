import { useEffect, useState } from "react";
import { PackagePlus } from "lucide-react";
import { Button } from "../../components/ui/button";
import { useSkillPacks } from "../state/useSkillPacks";
import { CreatePackForm } from "./CreatePackForm";
import { SkillPackList } from "./SkillPackList";
import { SkillPackWorkSurface } from "./SkillPackWorkSurface";

export function SkillPackManager() {
  const packsQuery = useSkillPacks();
  const packs = packsQuery.data ?? [];
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const selectedPack = packs.find((pack) => pack.id === selectedId) ?? packs[0] ?? null;
  const packId = selectedPack?.id ?? selectedId;

  useEffect(() => {
    if (!selectedId && packs[0]) setSelectedId(packs[0].id);
  }, [packs, selectedId]);

  return (
    <div className="skill-pack-manager">
      <header className="skill-pack-manager__header">
        <div>
          <h2>Skill Packs</h2>
          {selectedPack ? <p className="muted">{selectedPack.description || selectedPack.id}</p> : null}
        </div>
        <Button size="sm" variant="outline" type="button" onClick={() => setShowCreate((value) => !value)}>
          <PackagePlus size={14} />
          New skill pack
        </Button>
      </header>

      {showCreate ? <CreatePackForm onCreated={(id) => setSelectedId(id)} /> : null}

      <SkillPackList
        loading={packsQuery.isLoading}
        onSelect={setSelectedId}
        packs={packs}
        selectedId={selectedPack?.id ?? null}
      />

      {packId ? <SkillPackWorkSurface key={packId} packId={packId} /> : null}
    </div>
  );
}
