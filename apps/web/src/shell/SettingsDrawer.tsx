import { useState } from "react";
import { Link } from "@tanstack/react-router";
import type { DocTypeSummary } from "../types";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "../components/ui/sheet";

interface SettingsDrawerProps {
  docTypes: DocTypeSummary[];
  open: boolean;
  runtimeLabel: string;
  onOpenChange: (open: boolean) => void;
}

export function SettingsDrawer({ docTypes, onOpenChange, open, runtimeLabel }: SettingsDrawerProps) {
  const [selectedId, setSelectedId] = useState(docTypes[0]?.id ?? "");
  const selected = docTypes.find((docType) => docType.id === selectedId) ?? docTypes[0];

  return (
    <Sheet modal={false} open={open} onOpenChange={onOpenChange}>
      <SheetContent className="settings-drawer" side="right">
        <SheetHeader className="drawer-header">
          <SheetTitle>Settings</SheetTitle>
          <SheetDescription className="sr-only">
            Repository document type details, skill pack management, and runtime status.
          </SheetDescription>
        </SheetHeader>
          <section className="drawer-section">
            <h2>Document Types</h2>
            <div className="doctype-list">
              {docTypes.map((docType) => (
                <button
                  className={selected?.id === docType.id ? "active" : ""}
                  key={docType.id}
                  type="button"
                  onClick={() => setSelectedId(docType.id)}
                >
                  {docType.title}
                </button>
              ))}
            </div>
            {selected && (
              <div className="doctype-detail">
                {Object.entries(selected.resource_groups).map(([group, files]) => (
                  <section key={group}>
                    <h3>{group}</h3>
                    {files.length === 0 ? (
                      <p className="muted">No files</p>
                    ) : (
                      files.map((file) => (
                        <p className="resource-path" key={file}>
                          {file}
                        </p>
                      ))
                    )}
                  </section>
                ))}
                <h3>SKILL.md</h3>
                <pre>{selected.skill_markdown ?? ""}</pre>
              </div>
            )}
          </section>
          <section className="drawer-section">
            <h2>Skill Packs</h2>
            <p className="muted">
              Manage reusable materials, generated SKILL.md guidance, validation, and published versions in the dedicated management surface.
            </p>
            <Link className="command-chip" to="/management/skill-packs" aria-label="Open skill pack management">
              Open skill pack management
            </Link>
          </section>
          <section className="drawer-section">
            <h2>Runtime</h2>
            <p className="code-text">{runtimeLabel}</p>
          </section>
      </SheetContent>
    </Sheet>
  );
}
