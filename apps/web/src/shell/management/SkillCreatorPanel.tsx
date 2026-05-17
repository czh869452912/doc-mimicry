import { useState } from "react";
import { Bot } from "lucide-react";
import { Button } from "../../components/ui/button";
import { Textarea } from "../../components/ui/textarea";
import { useSkillCreatorGeneration } from "../state/useSkillPacks";

interface SkillCreatorPanelProps {
  packId: string;
}

export function SkillCreatorPanel({ packId }: SkillCreatorPanelProps) {
  const generatePack = useSkillCreatorGeneration(packId);
  const [creatorMessage, setCreatorMessage] = useState("Generate a skill from these materials.");

  return (
    <section className="skill-pack-panel">
      <h3>Skill Creator</h3>
      <Textarea value={creatorMessage} onChange={(event) => setCreatorMessage(event.target.value)} />
      <Button
        size="sm"
        type="button"
        disabled={generatePack.isPending || !creatorMessage.trim()}
        onClick={() => generatePack.mutate(creatorMessage)}
      >
        <Bot size={14} />
        Generate skill
      </Button>
      {generatePack.data?.paths.length ? <p className="muted">Updated {generatePack.data.paths.join(", ")}</p> : null}
    </section>
  );
}
