from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CreateTaskRequest(BaseModel):
    doc_type_id: str
    brief: str | None = None
    title: str | None = None
    description: str | None = None


class MessageAttachment(BaseModel):
    name: str
    markdown_path: str
    source_path: str | None = None
    conversion_report_path: str | None = None


class SendMessageRequest(BaseModel):
    message: str
    attachments: list[MessageAttachment] = Field(default_factory=list)


class PromptRequest(BaseModel):
    prompt: str
    metadata: dict[str, object] = Field(default_factory=dict)


class ImportTextRequest(BaseModel):
    name: str
    content: str


class ApproveOutlineRequest(BaseModel):
    outline_markdown: str


class PermissionAnswerRequest(BaseModel):
    decision: Literal["allow", "deny"]


class ReviseSelectionRequest(BaseModel):
    selected_text: str
    instruction: str


class UpdateDraftRequest(BaseModel):
    markdown: str
    force: bool = False


class CreateSkillPackRequest(BaseModel):
    id: str
    title: str
    description: str = ""


class AddSkillPackTextResourceRequest(BaseModel):
    group: Literal["examples", "specs", "checklists", "export-references"]
    name: str
    content: str


class UpdateSkillPackArtifactRequest(BaseModel):
    path: str
    content: str
    summary: str


class PublishSkillPackRequest(BaseModel):
    publish_note: str = ""
    acknowledged_warnings: list[str] = Field(default_factory=list)


class SkillCreatorMessageRequest(BaseModel):
    message: str
