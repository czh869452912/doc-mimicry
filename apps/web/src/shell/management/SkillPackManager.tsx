import { useEffect, useState } from "react";
import { Bot, CheckCircle2, FileText, PackagePlus, Play, Save, Upload } from "lucide-react";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { Textarea } from "../../components/ui/textarea";
import type { SkillPackResource } from "../../types";
import {
  useAddSkillPackFileResource,
  useAddSkillPackTextResource,
  useCreateSkillPack,
  usePublishSkillPack,
  useSkillCreatorGeneration,
  useSkillPackArtifact,
  useSkillPackResource,
  useSkillPackResources,
  useSkillPacks,
  useUpdateSkillPackArtifact,
  useValidateSkillPack,
} from "../state/useSkillPacks";

const RESOURCE_GROUPS: SkillPackResource["group"][] = ["examples", "specs", "checklists", "export-references"];

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

      <div className="skill-pack-list" aria-label="Skill packs">
        {packs.map((pack) => (
          <button
            className={pack.id === selectedPack?.id ? "active" : ""}
            key={pack.id}
            type="button"
            onClick={() => setSelectedId(pack.id)}
          >
            <span>{pack.title}</span>
            <Badge variant={pack.latest_version_id ? "secondary" : "outline"}>
              {pack.latest_version_id ? "published" : pack.draft_status}
            </Badge>
          </button>
        ))}
        {!packsQuery.isLoading && packs.length === 0 ? <p className="muted">No skill packs yet.</p> : null}
      </div>

      {packId ? <PackWorkSurface packId={packId} /> : null}
    </div>
  );
}

function CreatePackForm({ onCreated }: { onCreated: (id: string) => void }) {
  const createPack = useCreateSkillPack();
  const [id, setId] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");

  return (
    <form
      className="skill-pack-form"
      onSubmit={async (event) => {
        event.preventDefault();
        const pack = await createPack.mutateAsync({ id, title, description });
        onCreated(pack.id);
      }}
    >
      <label>
        <span>Pack id</span>
        <Input value={id} onChange={(event) => setId(event.target.value)} />
      </label>
      <label>
        <span>Pack title</span>
        <Input value={title} onChange={(event) => setTitle(event.target.value)} />
      </label>
      <label>
        <span>Pack description</span>
        <Input value={description} onChange={(event) => setDescription(event.target.value)} />
      </label>
      <Button size="sm" type="submit" disabled={createPack.isPending || !id.trim() || !title.trim()}>
        <Save size={14} />
        Create pack
      </Button>
    </form>
  );
}

function PackWorkSurface({ packId }: { packId: string }) {
  const addResource = useAddSkillPackTextResource(packId);
  const addFileResource = useAddSkillPackFileResource(packId);
  const resourcesQuery = useSkillPackResources(packId);
  const generatePack = useSkillCreatorGeneration(packId);
  const skillArtifact = useSkillPackArtifact(packId, "SKILL.md");
  const updateArtifact = useUpdateSkillPackArtifact(packId);
  const validatePack = useValidateSkillPack(packId);
  const publishPack = usePublishSkillPack(packId);
  const [resourceGroup, setResourceGroup] = useState<SkillPackResource["group"]>("examples");
  const [resourceName, setResourceName] = useState("material.txt");
  const [resourceContent, setResourceContent] = useState("");
  const [creatorMessage, setCreatorMessage] = useState("Generate a skill from these materials.");
  const [skillDraft, setSkillDraft] = useState("");
  const [publishNote, setPublishNote] = useState("");
  const [resourceError, setResourceError] = useState<string | null>(null);
  const [selectedResourceId, setSelectedResourceId] = useState<string | null>(null);
  const resourceDetail = useSkillPackResource(packId, selectedResourceId);
  const resources = resourcesQuery.data ?? [];
  const validationWarnings = validatePack.data?.warnings ?? [];

  useEffect(() => {
    if (skillArtifact.data?.content) setSkillDraft(skillArtifact.data.content);
  }, [skillArtifact.data?.content]);

  return (
    <div className="skill-pack-work">
      <section className="skill-pack-panel">
        <h3>Materials</h3>
        <div className="skill-pack-row">
          <label>
            <span>Group</span>
            <select value={resourceGroup} onChange={(event) => setResourceGroup(event.target.value as SkillPackResource["group"])}>
              {RESOURCE_GROUPS.map((group) => <option key={group} value={group}>{group}</option>)}
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
            <article className="skill-pack-resource-row" key={resource.id}>
              <div>
                <strong>{resource.original_filename}</strong>
                <p className="muted">{resource.group} · {resource.status}</p>
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
                disabled={!resource.markdown_path}
                onClick={() => setSelectedResourceId(resource.id)}
              >
                <FileText size={14} />
                View converted
              </Button>
            </article>
          ))}
        </div>
        {resourceDetail.data ? (
          <section className="skill-pack-resource-preview">
            <h4>{resourceDetail.data.original_filename}</h4>
            <pre>{resourceDetail.data.markdown}</pre>
          </section>
        ) : null}
      </section>

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

      <section className="skill-pack-panel">
        <h3>Validation</h3>
        {validatePack.data ? (
          <p className={validatePack.data.status === "passed" ? "status-ok" : "status-error"}>
            {validatePack.data.status}
          </p>
        ) : null}
        {validationWarnings.map((warning) => <p className="muted" key={warning}>{warning}</p>)}
        <div className="skill-pack-row">
          <Input value={publishNote} onChange={(event) => setPublishNote(event.target.value)} placeholder="Publish note" />
          <Button size="sm" variant="outline" type="button" onClick={() => validatePack.mutate()}>
            <CheckCircle2 size={14} />
            Validate
          </Button>
          <Button
            size="sm"
            type="button"
            disabled={publishPack.isPending}
            onClick={() => publishPack.mutate({ note: publishNote, warnings: validationWarnings })}
          >
            <Play size={14} />
            Publish
          </Button>
        </div>
      </section>
    </div>
  );
}
