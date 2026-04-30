from __future__ import annotations

from typing import Literal, TypedDict


class TaskRecord(TypedDict):
    id: str
    doc_type_id: str
    brief: str
    workspace_root: str
    created_at: str
    updated_at: str


class SessionRecord(TypedDict):
    id: str
    task_id: str
    status: Literal["idle", "running", "paused", "completed", "failed"]
    created_at: str
    updated_at: str
