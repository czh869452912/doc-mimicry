import {
  CheckCircle2,
  Download,
  FileText,
  FolderOpen,
  Play,
  Plus,
  RefreshCw,
  Save,
  Send,
  Upload,
  WandSparkles,
} from "lucide-react";
import { useEffect, useState, type SyntheticEvent } from "react";
import { api } from "../api";
import type {
  DocTypeSummary,
  SessionRecord,
  TaskRecord,
  TimelineEvent,
  WorkspaceFileContent,
  WorkspaceTree,
} from "../types";

export function WorkbenchPage() {
  const [docTypes, setDocTypes] = useState<DocTypeSummary[]>([]);
  const [selectedDocTypeId, setSelectedDocTypeId] = useState("prd");
  const [tasks, setTasks] = useState<TaskRecord[]>([]);
  const [sessions, setSessions] = useState<SessionRecord[]>([]);
  const [task, setTask] = useState<TaskRecord | null>(null);
  const [session, setSession] = useState<SessionRecord | null>(null);
  const [workspace, setWorkspace] = useState<WorkspaceTree | null>(null);
  const [openFile, setOpenFile] = useState<WorkspaceFileContent | null>(null);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [brief, setBrief] = useState("Write a PRD for the first usable document imitation loop.");
  const [message, setMessage] = useState("Refine the current draft.");
  const [inputName, setInputName] = useState("research.txt");
  const [inputContent, setInputContent] = useState("Users need clearer onboarding analytics.");
  const [outline, setOutline] = useState("");
  const [draft, setDraft] = useState("");
  const [selectedText, setSelectedText] = useState("");
  const [revisionInstruction, setRevisionInstruction] = useState("Make this passage more specific.");
  const [status, setStatus] = useState("");

  useEffect(() => {
    void loadInitialState();
  }, []);

  async function loadInitialState() {
    const [loadedDocTypes, loadedTasks] = await Promise.all([api.listDocTypes(), api.listTasks()]);
    setDocTypes(loadedDocTypes);
    setTasks(loadedTasks);
    if (loadedDocTypes[0]) {
      setSelectedDocTypeId(loadedDocTypes[0].id);
    }
    if (loadedTasks[0]) {
      await activateTask(loadedTasks[0]);
    }
  }

  async function activateTask(nextTask: TaskRecord) {
    const taskSessions = await api.listTaskSessions(nextTask.id);
    const nextSession = taskSessions[0] ?? null;
    setTask(nextTask);
    setSessions(taskSessions);
    setSession(nextSession);
    setOpenFile(null);
    await refreshTaskState(nextTask, nextSession);
  }

  async function activateSession(nextSession: SessionRecord) {
    setSession(nextSession);
    await refreshTaskState(task, nextSession);
  }

  async function refreshTaskState(nextTask: TaskRecord | null = task, nextSession: SessionRecord | null = session) {
    if (!nextTask) return;
    const [workspaceTree, draftResponse, outlineFile, nextTimeline] = await Promise.all([
      api.getWorkspace(nextTask.id),
      api.getDraft(nextTask.id),
      api.getWorkspaceFile(nextTask.id, "draft/outline.md").catch(() => null),
      nextSession ? api.getTimeline(nextSession.id) : Promise.resolve([]),
    ]);
    setWorkspace(workspaceTree);
    setDraft(draftResponse.markdown);
    setOutline(outlineFile?.content ?? "");
    setTimeline(nextTimeline);
  }

  async function ensureSession() {
    if (session) return session;
    if (!task) return null;
    const createdSession = await api.createSession(task.id);
    const taskSessions = await api.listTaskSessions(task.id);
    setSessions(taskSessions);
    setSession(createdSession);
    return createdSession;
  }

  async function perform(label: string, action: () => Promise<string | void>) {
    setStatus(`${label}...`);
    try {
      const result = await action();
      setStatus(result ?? `${label} completed`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : `${label} failed`);
    }
  }

  async function createTaskAndSession() {
    await perform("Create task", async () => {
      const createdTask = await api.createTask(selectedDocTypeId, brief);
      const createdSession = await api.createSession(createdTask.id);
      const loadedTasks = await api.listTasks();
      setTasks(loadedTasks);
      setSessions([createdSession]);
      setTask(createdTask);
      setSession(createdSession);
      setOpenFile(null);
      setTimeline([]);
      await refreshTaskState(createdTask, createdSession);
      return "Task and session ready";
    });
  }

  async function createSessionForTask() {
    await perform("Create session", async () => {
      if (!task) return "Select a task first";
      const createdSession = await api.createSession(task.id);
      const taskSessions = await api.listTaskSessions(task.id);
      setSessions(taskSessions);
      setSession(createdSession);
      await refreshTaskState(task, createdSession);
      return "Session ready";
    });
  }

  async function importTextInput() {
    await perform("Import input", async () => {
      if (!task) return "Create a task first";
      const activeSession = await ensureSession();
      await api.importTextInput(task.id, inputName, inputContent);
      await refreshTaskState(task, activeSession);
      return "Input converted to Markdown";
    });
  }

  async function startLoop() {
    await perform("Start loop", async () => {
      const activeSession = await ensureSession();
      if (!task || !activeSession) return "Create a task first";
      await api.startLoop(activeSession.id);
      await refreshTaskState(task, activeSession);
      return "Outline ready for approval";
    });
  }

  async function approveOutline() {
    await perform("Approve outline", async () => {
      if (!task || !session) return "Create a session first";
      await api.approveOutline(session.id, outline);
      await refreshTaskState(task, session);
      return "Draft generated";
    });
  }

  async function reviseSelection() {
    await perform("Revise selection", async () => {
      if (!task || !session) return "Create a session first";
      if (!selectedText.trim()) return "Select draft text first";
      await api.reviseSelection(session.id, selectedText, revisionInstruction);
      setSelectedText("");
      await refreshTaskState(task, session);
      return "Selection revised with checkpoint";
    });
  }

  async function runChecklist() {
    await perform("Run checklist", async () => {
      if (!task || !session) return "Create a session first";
      await api.runChecklist(session.id);
      await refreshTaskState(task, session);
      return "Checklist result written";
    });
  }

  async function exportMarkdown() {
    await perform("Export Markdown", async () => {
      if (!task || !session) return "Create a session first";
      const result = await api.exportMarkdown(session.id);
      await refreshTaskState(task, session);
      const artifactPath = result.artifact_path ?? "artifacts/prd-draft.md";
      await openWorkspaceFile(artifactPath);
      return "Markdown artifact exported";
    });
  }

  async function sendMessage() {
    await perform("Send message", async () => {
      if (!task || !session) return "Create a session first";
      await api.sendMessage(session.id, message);
      await refreshTaskState(task, session);
      return "Message processed";
    });
  }

  async function saveDraft() {
    await perform("Save draft", async () => {
      if (!task) return "Create a task first";
      setDraft((await api.updateDraft(task.id, draft)).markdown);
      await refreshTaskState(task, session);
      return "Draft saved";
    });
  }

  async function openWorkspaceFile(path: string) {
    if (!task) return;
    try {
      setOpenFile(await api.getWorkspaceFile(task.id, path));
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Could not open file");
    }
  }

  function captureSelection(event: SyntheticEvent<HTMLTextAreaElement>) {
    const target = event.currentTarget;
    setSelectedText(target.value.slice(target.selectionStart, target.selectionEnd));
  }

  return (
    <section className="workbench-grid">
      <aside className="panel rail">
        <div className="row">
          <h1>Workspace</h1>
          <button onClick={() => void perform("Refresh", () => refreshTaskState())} disabled={!task} title="Refresh">
            <RefreshCw size={16} />
          </button>
        </div>

        <label>Doc type</label>
        <select
          aria-label="Document type"
          value={selectedDocTypeId}
          onChange={(event) => setSelectedDocTypeId(event.target.value)}
        >
          {docTypes.map((docType) => (
            <option key={docType.id} value={docType.id}>
              {docType.id}
            </option>
          ))}
        </select>

        <label>Brief</label>
        <textarea value={brief} onChange={(event) => setBrief(event.target.value)} />
        <button onClick={() => void createTaskAndSession()}>
          <Plus size={16} /> Create task
        </button>

        <h3>Tasks</h3>
        <div className="file-list">
          {tasks.map((item) => (
            <button
              key={item.id}
              className={task?.id === item.id ? "active" : ""}
              onClick={() => void activateTask(item)}
            >
              <FileText size={16} />
              <span>{item.brief}</span>
            </button>
          ))}
        </div>

        <div className="row">
          <h3>Sessions</h3>
          <button onClick={() => void createSessionForTask()} disabled={!task} title="New session">
            <Plus size={16} />
          </button>
        </div>
        <div className="file-list">
          {sessions.map((item) => (
            <button
              key={item.id}
              className={session?.id === item.id ? "active" : ""}
              onClick={() => void activateSession(item)}
            >
              <FolderOpen size={16} />
              <span>
                {item.id} · {item.status}
              </span>
            </button>
          ))}
        </div>

        <h3>Import Text</h3>
        <input value={inputName} onChange={(event) => setInputName(event.target.value)} aria-label="Input name" />
        <textarea value={inputContent} onChange={(event) => setInputContent(event.target.value)} />
        <button onClick={() => void importTextInput()} disabled={!task}>
          <Upload size={16} /> Import
        </button>

        <h3>Files</h3>
        <div className="file-list workspace-files">
          {workspace?.files.map((file) => (
            <button key={file.path} onClick={() => void openWorkspaceFile(file.path)}>
              <FileText size={16} />
              <span>{file.path}</span>
              <small>{file.kind}</small>
            </button>
          ))}
        </div>
      </aside>

      <section className="panel timeline">
        <h1>Timeline</h1>
        <div className="action-grid">
          <button onClick={() => void startLoop()} disabled={!task}>
            <Play size={16} /> Start loop
          </button>
          <button onClick={() => void approveOutline()} disabled={!session || !outline.trim()}>
            <CheckCircle2 size={16} /> Approve outline
          </button>
          <button onClick={() => void runChecklist()} disabled={!session}>
            <CheckCircle2 size={16} /> Run checklist
          </button>
          <button onClick={() => void exportMarkdown()} disabled={!session}>
            <Download size={16} /> Export MD
          </button>
        </div>
        <p className="status-line">{status}</p>
        <div className="timeline-list">
          {timeline.map((event, index) => (
            <article key={`${event.id}-${index}`} className="timeline-event">
              <strong>{event.kind}</strong>
              <span>{event.actor}</span>
              <p>{event.summary}</p>
              {event.paths.length > 0 && <small>{event.paths.join(", ")}</small>}
            </article>
          ))}
        </div>
        <div className="composer">
          <input value={message} onChange={(event) => setMessage(event.target.value)} />
          <button onClick={() => void sendMessage()} disabled={!session}>
            <Send size={16} /> Send
          </button>
        </div>
      </section>

      <aside className="panel preview">
        <header>
          <h1>Authoring</h1>
          <button onClick={() => void saveDraft()} disabled={!task}>
            <Save size={16} /> Save
          </button>
        </header>

        <div className="split-preview">
          <section className="stack">
            <h2>{openFile?.path ?? "Open file"}</h2>
            <pre className="file-preview">{openFile?.content ?? ""}</pre>
          </section>

          <section className="stack">
            <h2>Draft</h2>
            <textarea
              className="draft-editor"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onSelect={captureSelection}
              onKeyUp={captureSelection}
              onMouseUp={captureSelection}
            />
            <div className="markdown-preview">
              {draft.split("\n").map((line, index) => (
                <p key={`${line}-${index}`}>{line || "\u00A0"}</p>
              ))}
            </div>
          </section>
        </div>

        <section className="stack">
          <h2>Outline</h2>
          <textarea className="compact-textarea" value={outline} onChange={(event) => setOutline(event.target.value)} />
          <div className="row">
            <input
              value={revisionInstruction}
              onChange={(event) => setRevisionInstruction(event.target.value)}
              aria-label="Revision instruction"
            />
            <button onClick={() => void reviseSelection()} disabled={!session || !selectedText.trim()}>
              <WandSparkles size={16} /> Revise
            </button>
          </div>
          <small className="muted selected-text">{selectedText || "No draft text selected"}</small>
        </section>
      </aside>
    </section>
  );
}
