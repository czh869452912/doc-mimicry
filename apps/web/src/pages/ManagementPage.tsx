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
          <button
            key={docType.id}
            className={selected?.id === docType.id ? "active" : ""}
            onClick={() => api.getDocType(docType.id).then(setSelected)}
          >
            {docType.title}
          </button>
        ))}
      </aside>
      <section className="panel detail-panel">
        <h2>{selected?.title ?? "No document type selected"}</h2>
        <p className="muted">
          Resource groups reflect files present in the doc-type pack. Original uploads stay auditable; agents consume
          converted Markdown and reports.
        </p>
        <div className="resource-grid">
          {selected &&
            Object.entries(selected.resource_groups).map(([group, files]) => (
              <section key={group} className="resource-card">
                <h3>{group}</h3>
                {files.length === 0 ? (
                  <p className="muted">No files</p>
                ) : (
                  files.map((file) => (
                    <p key={file} className="resource-path">
                      {file}
                    </p>
                  ))
                )}
              </section>
            ))}
        </div>
        <h3>SKILL.md</h3>
        <pre>{selected?.skill_markdown ?? ""}</pre>
      </section>
      <aside className="panel">
        <h2>Skill Creator</h2>
        <p className="muted">
          Phase 2 keeps this surface read-only. Interactive skill creation belongs to the next management iteration.
        </p>
      </aside>
    </section>
  );
}
