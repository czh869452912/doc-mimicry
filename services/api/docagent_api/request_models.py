from __future__ import annotations

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


class ReviseSelectionRequest(BaseModel):
    selected_text: str
    instruction: str


class UpdateDraftRequest(BaseModel):
    markdown: str
    force: bool = False
