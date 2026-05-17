import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Play } from "lucide-react";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { usePublishSkillPack, useValidateSkillPack } from "../state/useSkillPacks";

interface ValidationPublishPanelProps {
  packId: string;
}

export function ValidationPublishPanel({ packId }: ValidationPublishPanelProps) {
  const validatePack = useValidateSkillPack(packId);
  const publishPack = usePublishSkillPack(packId);
  const [publishNote, setPublishNote] = useState("");
  const [acknowledgedWarnings, setAcknowledgedWarnings] = useState<string[]>([]);
  const validationWarnings = useMemo(() => validatePack.data?.warnings ?? [], [validatePack.data?.warnings]);
  const allWarningsAcknowledged = validationWarnings.every((warning) => acknowledgedWarnings.includes(warning));
  const canPublish = !publishPack.isPending && validatePack.data?.status === "passed" && allWarningsAcknowledged;

  useEffect(() => {
    setAcknowledgedWarnings([]);
  }, [packId, validationWarnings]);

  return (
    <section className="skill-pack-panel">
      <h3>Validation</h3>
      {validatePack.data ? (
        <p className={validatePack.data.status === "passed" ? "status-ok" : "status-error"}>
          {validatePack.data.status}
        </p>
      ) : null}
      {validationWarnings.map((warning) => (
        <label className="skill-pack-warning-ack" key={warning}>
          <input
            type="checkbox"
            checked={acknowledgedWarnings.includes(warning)}
            onChange={(event) => {
              setAcknowledgedWarnings((current) =>
                event.target.checked
                  ? [...new Set([...current, warning])]
                  : current.filter((item) => item !== warning),
              );
            }}
          />
          <span>{warning}</span>
        </label>
      ))}
      <div className="skill-pack-row">
        <Input value={publishNote} onChange={(event) => setPublishNote(event.target.value)} placeholder="Publish note" />
        <Button size="sm" variant="outline" type="button" onClick={() => validatePack.mutate()}>
          <CheckCircle2 size={14} />
          Validate
        </Button>
        <Button
          size="sm"
          type="button"
          disabled={!canPublish}
          onClick={() => publishPack.mutate({ note: publishNote, acknowledgedWarnings })}
        >
          <Play size={14} />
          Publish
        </Button>
      </div>
    </section>
  );
}
