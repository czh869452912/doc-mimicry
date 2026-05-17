import { ResourcePanel } from "./ResourcePanel";
import { SkillArtifactEditor } from "./SkillArtifactEditor";
import { SkillCreatorPanel } from "./SkillCreatorPanel";
import { ValidationPublishPanel } from "./ValidationPublishPanel";

interface SkillPackWorkSurfaceProps {
  packId: string;
}

export function SkillPackWorkSurface({ packId }: SkillPackWorkSurfaceProps) {
  return (
    <div className="skill-pack-work">
      <ResourcePanel packId={packId} />
      <SkillCreatorPanel packId={packId} />
      <SkillArtifactEditor packId={packId} />
      <ValidationPublishPanel packId={packId} />
    </div>
  );
}
