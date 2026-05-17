import { useEffect, useState } from "react";
import { FileText, Upload } from "lucide-react";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Textarea } from "../../components/ui/textarea";
import type { SkillPackResource } from "../../types";
import {
  useAddSkillPackFileResource,
  useAddSkillPackTextResource,
  useSkillPackResource,
  useSkillPackResources,
} from "../state/useSkillPacks";

const RESOURCE_GROUPS: SkillPackResource["group"][] = ["examples", "specs", "checklists", "export-references"];

interface ResourcePanelProps {
  packId: string;
}

export function ResourcePanel({ packId }: ResourcePanelProps) {
  const addResource = useAddSkillPackTextResource(packId);
  const addFileResource = useAddSkillPackFileResource(packId);
  const resourcesQuery = useSkillPackResources(packId);
  const [resourceGroup, setResourceGroup] = useState<SkillPackResource["group"]>("examples");
  const [resourceName, setResourceName] = useState("material.txt");
  const [resourceContent, setResourceContent] = useState("");
  const [resourceError, setResourceError] = useState<string | null>(null);
  const [selectedResourceId, setSelectedResourceId] = useState<string | null>(null);
  const resourceDetail = useSkillPackResource(packId, selectedResourceId);
  const resources = resourcesQuery.data ?? [];

  useEffect(() => {
    setSelectedResourceId(null);
  }, [packId]);

  return (
    <section className="skill-pack-panel">
      <h3>Materials</h3>
      <div className="skill-pack-row">
        <label>
          <span>Group</span>
          <select
            value={resourceGroup}
            onChange={(event) => setResourceGroup(event.target.value as SkillPackResource["group"])}
          >
            {RESOURCE_GROUPS.map((group) => (
              <option key={group} value={group}>
                {group}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Name</span>
          <Input value={resourceName} onChange={(event) => setResourceName(event.target.value)} />
        </label>
      </div>
      <Label htmlFor="resource-content">Material text</Label>
      <Textarea id="resource-content" value={resourceContent} onChange={(event) => setResourceContent(event.target.value)} />
      <Label htmlFor="resource-file">Upload material file</Label>
      <Input
        aria-label="Upload material file"
        id="resource-file"
        type="file"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) {
            setResourceError(null);
            addFileResource.mutate(
              { group: resourceGroup, file },
              {
                onError: (caught) => {
                  setResourceError(caught instanceof Error ? caught.message : "Material upload failed.");
                },
              },
            );
          }
          event.target.value = "";
        }}
      />
      {resourceError ? <p className="status-error">{resourceError}</p> : null}
      <Button
        size="sm"
        variant="outline"
        type="button"
        disabled={addResource.isPending || addFileResource.isPending || !resourceContent.trim()}
        onClick={() => addResource.mutate({ group: resourceGroup, name: resourceName, content: resourceContent })}
      >
        <Upload size={14} />
        Add material
      </Button>
      <div className="skill-pack-resource-list" aria-label="Pack resources">
        {resources.map((resource) => (
          <ResourceRow
            key={resource.id}
            onPreview={() => setSelectedResourceId(resource.id)}
            resource={resource}
            selected={resource.id === selectedResourceId}
          />
        ))}
      </div>
      {resourceDetail.data ? (
        <section className="skill-pack-resource-preview">
          <h4>{resourceDetail.data.original_filename}</h4>
          <pre>{resourceDetail.data.markdown}</pre>
        </section>
      ) : null}
    </section>
  );
}

function ResourceRow({
  onPreview,
  resource,
  selected,
}: {
  onPreview: () => void;
  resource: SkillPackResource;
  selected: boolean;
}) {
  return (
    <article className={selected ? "skill-pack-resource-row active" : "skill-pack-resource-row"}>
      <div>
        <strong>{resource.original_filename}</strong>
        <p className="muted">
          {resource.group} · {resource.status}
        </p>
        {(resource.warnings ?? []).map((warning) => (
          <p className="status-warning" key={`${resource.id}-${warning.type}-${warning.message}`}>
            {warning.message}
          </p>
        ))}
      </div>
      <Button
        size="sm"
        variant="outline"
        type="button"
        aria-label={`View converted ${resource.original_filename}`}
        aria-pressed={selected}
        disabled={!resource.markdown_path}
        onClick={onPreview}
      >
        <FileText size={14} />
        View converted
      </Button>
    </article>
  );
}
