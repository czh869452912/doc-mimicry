from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


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
    pack_version_id: str | None = None
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
    markdown_path: str | None = None
    conversion_report_path: str
    original_filename: str
    created_at: str
    warnings: list[dict[str, Any]] = Field(default_factory=list)
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


class AcpEventResponse(BaseModel):
    id: str
    session_id: str
    sequence: int
    event_type: str
    payload: dict[str, Any]
    projection: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class SkillPackSummaryResponse(BaseModel):
    id: str
    title: str
    description: str
    draft_status: str
    latest_version_id: str | None = None


class SkillPackResourceResponse(BaseModel):
    id: str
    pack_id: str
    group: str
    original_filename: str
    source_path: str
    markdown_path: str | None = None
    conversion_report_path: str
    status: str
    summary: str = ""
    warnings: list[dict[str, Any]] = Field(default_factory=list)


class SkillPackResourceDetailResponse(SkillPackResourceResponse):
    markdown: str = ""
    conversion_report: dict[str, Any] = Field(default_factory=dict)


class SkillPackArtifactResponse(BaseModel):
    pack_id: str
    path: str
    content: str


class SkillPackValidationResponse(BaseModel):
    status: str
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SkillPackVersionResponse(BaseModel):
    id: str
    pack_id: str
    version: str
    manifest: dict[str, Any]
    validation: dict[str, Any]
    publish_note: str
    created_at: str | None = None


class SkillCreatorEventResponse(BaseModel):
    id: int
    session_id: str
    event_type: str
    payload: dict[str, Any]
    projection: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class SkillCreatorSessionResponse(BaseModel):
    id: str
    pack_id: str
    session_scope: str
    status: str
    runtime: str | None = None
    runtime_session_id: str | None = None


class SkillCreatorRunResponse(BaseModel):
    paths: list[str]
