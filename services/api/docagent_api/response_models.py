from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    runtime: str


class DocTypeSummaryResponse(BaseModel):
    id: str
    title: str
    has_skill: bool
    resource_groups: dict[str, list[str]]
    skill_markdown: str | None = None


class TaskResponse(BaseModel):
    id: str
    doc_type_id: str
    brief: str
    title: str
    description: str
    workspace_root: str
    created_at: str
    updated_at: str


class SessionResponse(BaseModel):
    id: str
    task_id: str
    status: str
    created_at: str
    updated_at: str


class WorkspaceFileSummary(BaseModel):
    path: str
    group: str
    kind: str


class WorkspaceResponse(BaseModel):
    task_id: str
    root: str
    files: list[WorkspaceFileSummary]


class WorkspaceFileContentResponse(BaseModel):
    path: str
    content: str


class DraftResponse(BaseModel):
    task_id: str
    markdown: str


class ImportedInputResponse(BaseModel):
    id: str
    status: str
    source_path: str
    markdown_path: str
    conversion_report_path: str
    original_filename: str
    created_at: str
    event: dict | None = None


class LoopActionResponse(BaseModel):
    session_id: str
    next_state: str | None = None
    event_count: int | None = None
    raw_event_count: int | None = None
    paths: list[str] | None = None
    artifact_path: str | None = None
    accepted: bool | None = None
    status: str | None = None


class TimelineEventResponse(BaseModel):
    id: str
    session_id: str
    task_id: str
    actor: str
    kind: str
    raw_event_id: str | None
    summary: str
    paths: list[str]
    status: str
    created_at: str
