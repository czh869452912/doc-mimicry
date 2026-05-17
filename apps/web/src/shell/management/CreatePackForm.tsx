import { useState } from "react";
import { Save } from "lucide-react";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { useCreateSkillPack } from "../state/useSkillPacks";

interface CreatePackFormProps {
  onCreated: (id: string) => void;
}

export function CreatePackForm({ onCreated }: CreatePackFormProps) {
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
