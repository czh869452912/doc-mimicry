import { ChevronRight, FileText, Folder, MessageSquare, Plus } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Tree, type NodeRendererProps } from "react-arborist";
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
  const [description, setDescription] = useState("Write a PRD for the first usable document imitation loop.");
  const [title, setTitle] = useState("First usable imitation loop PRD");
  const [docTypeId, setDocTypeId] = useState(docTypes[0]?.id ?? "prd");
  const selectedId = activeSession ? `session:${activeSession.id}` : activeTask ? `task:${activeTask.id}` : undefined;
  const initialOpenState = useMemo(() => Object.fromEntries(nodes.map((node) => [node.id, true])), [nodes]);

  useEffect(() => {
    if (docTypes.length === 0) return;
    if (!docTypes.some((docType) => docType.id === docTypeId)) {
      setDocTypeId(docTypes[0].id);
    }
  }, [docTypeId, docTypes]);

  async function submitCreate() {
    await onCreateWorkspace(docTypeId, { description, title });
    setCreating(false);
  }

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
          className="workspace-create"
          onSubmit={(event) => {
            event.preventDefault();
            void submitCreate();
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
              value={title}
              onChange={(event) => setTitle(event.target.value)}
            />
            <FieldDescription>Shown in the workspace list.</FieldDescription>
          </Field>
          <Field>
            <FieldLabel htmlFor="workspace-description">Description</FieldLabel>
            <Textarea
              aria-label="Description"
              id="workspace-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
            <FieldDescription>Used as the agent brief inside the workspace.</FieldDescription>
          </Field>
          <Button type="submit">
            Create workspace
          </Button>
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
            if (data.kind === "session" && data.sessionId) onSelectSession(data.sessionId);
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
      {data.status && <span className="workspace-node__status">{data.status}</span>}
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
  if (kind === "session") return <MessageSquare size={14} />;
  return <FileText size={14} />;
}
