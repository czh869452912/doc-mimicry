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
  pack_version_id?: string | null;
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
  raw_acp_event?: AcpEvent;
}

export interface AcpEvent {
  id: string;
  session_id: string;
  sequence: number;
  event_type: string;
  payload: Record<string, unknown>;
  projection: Record<string, unknown>;
  created_at: string;
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
  markdown_path: string | null;
  conversion_report_path: string;
  original_filename: string;
  created_at: string;
  warnings?: Array<{ type: string; message: string; location: string | null }>;
  event?: TimelineEvent;
}

export interface MessageAttachment {
  name: string;
  markdown_path: string;
  source_path?: string | null;
  conversion_report_path?: string | null;
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

export interface SkillPackSummary {
  id: string;
  title: string;
  description: string;
  draft_status: string;
  latest_version_id?: string | null;
}

export interface SkillPackResource {
  id: string;
  pack_id: string;
  group: "examples" | "specs" | "checklists" | "export-references";
  original_filename: string;
  markdown_path?: string | null;
  conversion_report_path: string;
  status: "ready" | "warning" | "failed" | "unsupported";
  summary: string;
}

export interface SkillPackArtifact {
  pack_id: string;
  path: string;
  content: string;
}

export interface SkillPackVersion {
  id: string;
  pack_id: string;
  version: string;
  publish_note: string;
  manifest: Record<string, unknown>;
  validation: Record<string, unknown>;
  created_at?: string | null;
}

export interface SkillCreatorSession {
  id: string;
  pack_id: string;
  session_scope: "pack-management";
  status: string;
  runtime?: string | null;
  runtime_session_id?: string | null;
}

export interface SkillCreatorRunResult {
  paths: string[];
}

export interface SkillPackValidation {
  status: "passed" | "failed";
  errors: string[];
  warnings: string[];
}
