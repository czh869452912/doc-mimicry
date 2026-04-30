import { useEffect, useState } from "react";
import { api } from "../api";
import type { DocTypeSummary } from "../types";

export function ManagementPage() {
  const [docTypes, setDocTypes] = useState<DocTypeSummary[]>([]);
  const [selected, setSelected] = useState<DocTypeSummary | null>(null);

  useEffect(() => {
    api.listDocTypes().then(async (items) => {
      setDocTypes(items);
      if (items[0]) {
        setSelected(await api.getDocType(items[0].id));
      }
    });
  }, []);

  return (
    <section className="management-grid">
      <aside className="panel">
        <h1>Doc types</h1>
        {docTypes.map((docType) => (
          <button key={docType.id} onClick={() => api.getDocType(docType.id).then(setSelected)}>
            {docType.title}
          </button>
        ))}
      </aside>
      <section className="panel detail-panel">
        <h2>{selected?.title ?? "No document type selected"}</h2>
        <div className="resource-grid">
          {selected &&
            Object.entries(selected.resource_groups).map(([group, files]) => (
              <section key={group}>
                <h3>{group}</h3>
                {files.length === 0 ? <p className="muted">No files</p> : files.map((file) => <p key={file}>{file}</p>)}
              </section>
            ))}
        </div>
        <h3>SKILL.md</h3>
        <pre>{selected?.skill_markdown ?? ""}</pre>
      </section>
      <aside className="panel">
        <h2>Skill Creator</h2>
        <p className="muted">Conversation placeholder for building and revising document type packs.</p>
      </aside>
    </section>
  );
}
