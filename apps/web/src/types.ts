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
  workspace_root: string;
}

export interface SessionRecord {
  id: string;
  task_id: string;
  status: string;
}

export interface TimelineEvent {
  id: string;
  actor: string;
  kind: string;
  summary: string;
  paths: string[];
  status: string;
}
