import { useEffect, useState } from "react";
import { FileText } from "lucide-react";
import { Button } from "../../components/ui/button";
import { Textarea } from "../../components/ui/textarea";
import { useSkillPackArtifact, useUpdateSkillPackArtifact } from "../state/useSkillPacks";

interface SkillArtifactEditorProps {
  packId: string;
}

export function SkillArtifactEditor({ packId }: SkillArtifactEditorProps) {
  const skillArtifact = useSkillPackArtifact(packId, "SKILL.md");
  const updateArtifact = useUpdateSkillPackArtifact(packId);
  const [skillDraft, setSkillDraft] = useState("");

  useEffect(() => {
    setSkillDraft(skillArtifact.data?.content ?? "");
  }, [skillArtifact.data?.content]);

  return (
    <section className="skill-pack-panel">
      <h3>SKILL.md</h3>
      <Textarea className="skill-editor" value={skillDraft} onChange={(event) => setSkillDraft(event.target.value)} />
      <Button
        size="sm"
        variant="outline"
        type="button"
        disabled={updateArtifact.isPending || !skillDraft.trim()}
        onClick={() => updateArtifact.mutate({ path: "SKILL.md", content: skillDraft, summary: "Manual Skill Creator edit" })}
      >
        <FileText size={14} />
        Save SKILL.md
      </Button>
    </section>
  );
}
