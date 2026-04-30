import { Save, Send } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import type { DocTypeSummary, SessionRecord, TaskRecord, TimelineEvent } from "../types";

export function WorkbenchPage() {
  const [docTypes, setDocTypes] = useState<DocTypeSummary[]>([]);
  const [task, setTask] = useState<TaskRecord | null>(null);
  const [session, setSession] = useState<SessionRecord | null>(null);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [brief, setBrief] = useState("Write a PRD for the first usable document imitation loop.");
  const [message, setMessage] = useState("Start drafting from the brief.");
  const [draft, setDraft] = useState("");

  useEffect(() => {
    api.listDocTypes().then(setDocTypes);
  }, []);

  async function createTaskAndSession() {
    const createdTask = await api.createTask("prd", brief);
    const createdSession = await api.createSession(createdTask.id);
    setTask(createdTask);
    setSession(createdSession);
    setTimeline([]);
    setDraft("");
  }

  async function sendMessage() {
    if (!session || !task) return;
    await api.sendMessage(session.id, message);
    setTimeline(await api.getTimeline(session.id));
    setDraft((await api.getDraft(task.id)).markdown);
  }

  async function saveDraft() {
    if (!task) return;
    setDraft((await api.updateDraft(task.id, draft)).markdown);
  }

  return (
    <section className="workbench-grid">
      <aside className="panel rail">
        <h1>Workspace</h1>
        <label>Doc type</label>
        <select aria-label="Document type">
          {docTypes.map((docType) => (
            <option key={docType.id}>{docType.id}</option>
          ))}
        </select>
        <label>Brief</label>
        <textarea value={brief} onChange={(event) => setBrief(event.target.value)} />
        <button onClick={createTaskAndSession}>Create task</button>
        <div className="meta-list">
          <p>Task: {task?.id ?? "none"}</p>
          <p>Session: {session?.id ?? "none"}</p>
          <p>Inputs: markdown-first</p>
          <p>Versions: workspace-backed</p>
          <p>Artifacts: pending</p>
        </div>
      </aside>
      <section className="panel timeline">
        <h1>Timeline</h1>
        <div className="timeline-list">
          {timeline.map((event) => (
            <article key={event.id} className="timeline-event">
              <strong>{event.kind}</strong>
              <span>{event.actor}</span>
              <p>{event.summary}</p>
              {event.paths.length > 0 && <small>{event.paths.join(", ")}</small>}
            </article>
          ))}
        </div>
        <div className="composer">
          <input value={message} onChange={(event) => setMessage(event.target.value)} />
          <button onClick={sendMessage} disabled={!session}>
            <Send size={16} /> Send
          </button>
        </div>
      </section>
      <aside className="panel preview">
        <header>
          <h1>Draft</h1>
          <button onClick={saveDraft} disabled={!task}>
            <Save size={16} /> Save
          </button>
        </header>
        <textarea value={draft} onChange={(event) => setDraft(event.target.value)} />
        <section className="markdown-preview">
          {draft.split("\n").map((line, index) => (
            <p key={`${line}-${index}`}>{line || "\u00A0"}</p>
          ))}
        </section>
      </aside>
    </section>
  );
}
