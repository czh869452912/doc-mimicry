import { ChevronRight, FileText, Folder, MessageSquare, Plus } from "lucide-react";
import { useMemo, useState } from "react";
import { Tree, type NodeRendererProps } from "react-arborist";
import type { DocTypeSummary, SessionRecord, TaskRecord } from "../../types";
import type { WorkspaceTreeNode } from "../state/useWorkspaces";

interface WorkspacePaneProps {
  activeSession: SessionRecord | null;
  activeTask: TaskRecord | null;
  docTypes: DocTypeSummary[];
  error: string | null;
  loading: boolean;
  nodes: WorkspaceTreeNode[];
  onCreateWorkspace: (docTypeId: string, brief: string) => Promise<void>;
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
  onCreateWorkspace,
  onOpenFile,
  onSelectSession,
  onSelectTask,
}: WorkspacePaneProps) {
  const [creating, setCreating] = useState(false);
  const [brief, setBrief] = useState("Write a PRD for the first usable document imitation loop.");
  const [docTypeId, setDocTypeId] = useState(docTypes[0]?.id ?? "prd");
  const selectedId = activeSession ? `session:${activeSession.id}` : activeTask ? `task:${activeTask.id}` : undefined;
  const initialOpenState = useMemo(() => Object.fromEntries(nodes.map((node) => [node.id, true])), [nodes]);

  async function submitCreate() {
    await onCreateWorkspace(docTypeId, brief);
    setCreating(false);
  }

  return (
    <div className="workspace-pane">
      <div className="pane-header">
        <span className="caption-uppercase">Workspaces</span>
        <button className="icon-button" type="button" aria-label="Create workspace" onClick={() => setCreating(true)}>
          <Plus size={14} />
        </button>
      </div>

      {creating && (
        <form
          className="workspace-create"
          onSubmit={(event) => {
            event.preventDefault();
            void submitCreate();
          }}
        >
          <label>
            <span>Document type</span>
            <select value={docTypeId} onChange={(event) => setDocTypeId(event.target.value)}>
              {docTypes.map((docType) => (
                <option key={docType.id} value={docType.id}>
                  {docType.title}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Brief</span>
            <textarea value={brief} onChange={(event) => setBrief(event.target.value)} />
          </label>
          <button className="primary-button" type="submit">
            Create workspace
          </button>
        </form>
      )}

      {loading && <p className="pane-note">Loading workspaces...</p>}
      {error && <p className="pane-note pane-note--error">{error}</p>}
      {!loading && nodes.length === 0 && (
        <button className="empty-card" type="button" onClick={() => setCreating(true)}>
          Create your first workspace
        </button>
      )}
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
            if (data.kind === "task" && data.taskId) onSelectTask(data.taskId);
            if (data.kind === "session" && data.sessionId) onSelectSession(data.sessionId);
            if (data.kind === "folder" && data.path) onOpenFile(data.path);
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

function iconFor(kind: WorkspaceTreeNode["kind"]) {
  if (kind === "task" || kind === "folder") return <Folder size={14} />;
  if (kind === "session") return <MessageSquare size={14} />;
  return <FileText size={14} />;
}
