import { zodResolver } from "@hookform/resolvers/zod";
import { ChevronRight, FileText, Folder, MessageSquare, Plus } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { Tree, type NodeRendererProps } from "react-arborist";
import { z } from "zod";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
} from "../../components/ui/empty";
import { Field, FieldDescription, FieldLabel } from "../../components/ui/field";
import { Input } from "../../components/ui/input";
import { Textarea } from "../../components/ui/textarea";
import type { DocTypeSummary, SessionRecord, TaskRecord } from "../../types";
import type { CreateWorkspaceInput, WorkspaceTreeNode } from "../state/useWorkspaces";

const createWorkspaceSchema = z.object({
  title: z.string().trim().min(1, "Title is required"),
  description: z.string().trim().min(1, "Description is required"),
});

interface WorkspacePaneProps {
  activeSession: SessionRecord | null;
  activeTask: TaskRecord | null;
  docTypes: DocTypeSummary[];
  error: string | null;
  loading: boolean;
  nodes: WorkspaceTreeNode[];
  sessions: SessionRecord[];
  onCreateSession: () => Promise<void>;
  onCreateWorkspace: (docTypeId: string, input: CreateWorkspaceInput) => Promise<void>;
  onOpenFile: (path: string) => void;
  onSelectSession: (sessionId: string) => void;
  onSelectTask: (taskId: string) => void;
}

export function WorkspacePane({
  activeSession,
  activeTask,
  docTypes,
  error,
  loading,
  nodes,
  sessions,
  onCreateSession,
  onCreateWorkspace,
  onOpenFile,
  onSelectSession,
  onSelectTask,
}: WorkspacePaneProps) {
  const [creating, setCreating] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [docTypeId, setDocTypeId] = useState(docTypes[0]?.id ?? "prd");
  const selectedId = activeTask ? `task:${activeTask.id}` : undefined;
  // react-arborist only reads initialOpenState on first mount — recomputing on every
  // nodes change is wasteful and has no effect after the initial render.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const initialOpenState = useMemo(() => Object.fromEntries(nodes.map((node) => [node.id, true])), []);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<z.infer<typeof createWorkspaceSchema>>({
    resolver: zodResolver(createWorkspaceSchema),
    defaultValues: {
      title: "",
      description: "",
    },
  });

  useEffect(() => {
    if (docTypes.length === 0) return;
    if (!docTypes.some((docType) => docType.id === docTypeId)) {
      setDocTypeId(docTypes[0].id);
    }
  }, [docTypeId, docTypes]);

  return (
    <div className="workspace-pane">
      <div className="pane-header">
        <span className="caption-uppercase">Workspaces</span>
        <Button className="icon-button" variant="outline" aria-label="Create workspace" onClick={() => setCreating(true)}>
          <Plus size={14} />
        </Button>
      </div>

      {creating && (
        <form
          aria-label="Create workspace"
          className="workspace-create"
          onSubmit={(event) => {
            setSubmitError(null);
            void handleSubmit(async (values) => {
              try {
                await onCreateWorkspace(docTypeId, { title: values.title, description: values.description });
                reset();
                setCreating(false);
              } catch (err) {
                setSubmitError(err instanceof Error ? err.message : "Failed to create workspace");
              }
            })(event);
          }}
        >
          <Field>
            <FieldLabel htmlFor="workspace-doc-type">Document type</FieldLabel>
            <select id="workspace-doc-type" value={docTypeId} onChange={(event) => setDocTypeId(event.target.value)}>
              {docTypes.map((docType) => (
                <option key={docType.id} value={docType.id}>
                  {docType.title}
                </option>
              ))}
            </select>
          </Field>
          <Field>
            <FieldLabel htmlFor="workspace-title">Title</FieldLabel>
            <Input
              aria-label="Title"
              id="workspace-title"
              {...register("title")}
            />
            {errors.title && (
              <p className="pane-note pane-note--error">{errors.title.message}</p>
            )}
            <FieldDescription>Shown in the workspace list.</FieldDescription>
          </Field>
          <Field>
            <FieldLabel htmlFor="workspace-description">Description</FieldLabel>
            <Textarea
              aria-label="Description"
              id="workspace-description"
              {...register("description")}
            />
            {errors.description && (
              <p className="pane-note pane-note--error">{errors.description.message}</p>
            )}
            <FieldDescription>Used as the agent brief inside the workspace.</FieldDescription>
          </Field>
          {submitError && <p className="pane-note pane-note--error">{submitError}</p>}
          <div className="workspace-create__actions">
            <Button type="button" variant="outline" onClick={() => { reset(); setCreating(false); }}>
              Cancel
            </Button>
            <Button type="submit">Create workspace</Button>
          </div>
        </form>
      )}

      {loading && <p className="pane-note">Loading workspaces...</p>}
      {error && <p className="pane-note pane-note--error">{error}</p>}
      {!loading && nodes.length === 0 && (
        <Empty>
          <EmptyContent>
            <EmptyDescription>No workspaces yet.</EmptyDescription>
            <Button variant="outline" onClick={() => setCreating(true)}>
              Create workspace
            </Button>
          </EmptyContent>
        </Empty>
      )}
      {activeTask && (
        <section className="workspace-section">
          <div className="pane-header">
            <span className="caption-uppercase">Sessions</span>
            <Button variant="outline" aria-label="New session" onClick={() => void onCreateSession()}>
              <Plus size={14} />
            </Button>
          </div>
          <div className="session-list">
            {sessions.length > 0 ? (
              <SessionList activeSession={activeSession} sessions={sessions} onSelectSession={onSelectSession} />
            ) : (
              <p className="pane-note">No sessions yet.</p>
            )}
          </div>
        </section>
      )}
      {nodes.length > 0 && <span className="caption-uppercase">Workspace files</span>}
      {nodes.length > 0 && (
        <Tree
          data={nodes}
          height={680}
          indent={14}
          initialOpenState={initialOpenState}
          rowHeight={30}
          selection={selectedId}
          width="100%"
          onActivate={(node) => {
            const data = node.data;
            if (data.kind === "task" && data.taskId) {
              node.toggle();
              onSelectTask(data.taskId);
            }
            if (data.kind === "folder") node.toggle();
            if (data.kind === "file" && data.path) onOpenFile(data.path);
          }}
        >
          {(props) => <WorkspaceNode {...props} />}
        </Tree>
      )}
    </div>
  );
}

function WorkspaceNode({ node, style }: NodeRendererProps<WorkspaceTreeNode>) {
  const data = node.data;
  return (
    <div className={`workspace-node workspace-node--${data.kind}`} style={style}>
      <span className="workspace-node__chevron">{node.isInternal ? <ChevronRight size={13} /> : null}</span>
      <span className="workspace-node__icon">{iconFor(data.kind)}</span>
      <span className="workspace-node__label">{data.name}</span>
      {data.kind === "task" && data.taskId && <span className="workspace-node__status">task</span>}
    </div>
  );
}

function SessionList({
  activeSession,
  onSelectSession,
  sessions,
}: {
  activeSession: SessionRecord | null;
  onSelectSession: (sessionId: string) => void;
  sessions: SessionRecord[];
}) {
  return (
    <>
      {sessions.map((session) => (
        <button
          className={`session-item ${session.id === activeSession?.id ? "session-item--active" : ""}`.trim()}
          key={session.id}
          type="button"
          onClick={() => onSelectSession(session.id)}
        >
          <MessageSquare size={14} />
          <span>{session.id}</span>
          <Badge variant="secondary">{session.status}</Badge>
        </button>
      ))}
    </>
  );
}

function iconFor(kind: WorkspaceTreeNode["kind"]) {
  if (kind === "task" || kind === "folder") return <Folder size={14} />;
  return <FileText size={14} />;
}
