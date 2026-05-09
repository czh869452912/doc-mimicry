export interface DocTypeSummary {
  id: string;
  title: string;
  has_skill: boolean;
  resource_groups: Record<string, string[]>;
  skill_markdown?: string;
}

export interface TaskRecord {
  id: string;
  doc_type_id: string;
  brief: string;
  title?: string;
  description?: string;
  workspace_root: string;
  created_at: string;
  updated_at: string;
}

export interface SessionRecord {
  id: string;
  task_id: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface TimelineEvent {
  id: string;
  session_id: string;
  task_id: string;
  actor: string;
  kind: string;
  raw_event_id: string | null;
  summary: string;
  paths: string[];
  status: string;
  created_at?: string;
}

export interface WorkspaceFile {
  path: string;
  group: string;
  kind: string;
}

export interface WorkspaceTree {
  task_id: string;
  root: string;
  files: WorkspaceFile[];
}

export interface WorkspaceFileContent {
  path: string;
  content: string;
}

export interface ImportedInput {
  id: string;
  status: string;
  source_path: string;
  markdown_path: string;
  conversion_report_path: string;
  original_filename: string;
  created_at: string;
  event?: TimelineEvent;
}

export interface LoopActionResult {
  session_id: string;
  next_state?: string | null;
  event_count?: number | null;
  raw_event_count?: number | null;
  paths?: string[] | null;
  artifact_path?: string | null;
  accepted?: boolean | null;
  status?: string | null;
}
