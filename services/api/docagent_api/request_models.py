from __future__ import annotations

from pydantic import BaseModel


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
    attachments: list[MessageAttachment] = []


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
