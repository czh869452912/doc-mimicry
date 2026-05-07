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
  actor: string;
  kind: string;
  summary: string;
  paths: string[];
  status: string;
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
  next_state?: string;
  event_count?: number;
  paths?: string[];
  artifact_path?: string;
}
