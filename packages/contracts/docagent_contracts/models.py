from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ResourceScope(str, Enum):
    TASK_INPUT = "task_input"
    DOCTYPE_EXAMPLE = "doctype_example"
    DOCTYPE_SPEC = "doctype_spec"
    DOCTYPE_CHECKLIST = "doctype_checklist"
    EXPORT_REFERENCE = "export_reference"


class ResourceStatus(str, Enum):
    PENDING = "pending"
    CONVERTING = "converting"
    CONVERTED = "converted"
    FAILED = "failed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class PackResourceGroup(str, Enum):
    EXAMPLES = "examples"
    SPECS = "specs"
    CHECKLISTS = "checklists"
    EXPORT_REFERENCES = "export-references"


class SkillPackResourceStatus(str, Enum):
    READY = "ready"
    WARNING = "warning"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"


class ConversionEngine(str, Enum):
    DOCLING = "docling"
    MARKITDOWN = "markitdown"
    PANDOC = "pandoc"
    MINERU = "mineru"
    MARKER = "marker"
    MANUAL = "manual"
    UNKNOWN = "unknown"


class ConversionStatus(str, Enum):
    SUCCEEDED = "succeeded"
    SUCCEEDED_WITH_WARNINGS = "succeeded_with_warnings"
    FAILED = "failed"


class TimelineActor(str, Enum):
    USER = "user"
    AGENT = "agent"
    TOOL = "tool"
    SYSTEM = "system"


class SemanticEventKind(str, Enum):
    USER_MESSAGE = "user_message"
    AGENT_MESSAGE = "agent_message"
    READ_SKILL = "read_skill"
    ANALYZE_EXAMPLES = "analyze_examples"
    CONVERT_INPUT = "convert_input"
    BUILD_CONTEXT = "build_context"
    EXTRACT_STYLE = "extract_style"
    EXTRACT_STRUCTURE = "extract_structure"
    GENERATE_OUTLINE = "generate_outline"
    PROPOSE_OUTLINE = "propose_outline"
    APPROVE_OUTLINE = "approve_outline"
    UPDATE_DRAFT = "update_draft"
    REVISE_SELECTION = "revise_selection"
    CREATE_CHECKPOINT = "create_checkpoint"
    RUN_CHECKLIST = "run_checklist"
    EXPORT_MARKDOWN = "export_markdown"
    EXPORT_DOCX = "export_docx"
    EXPORT_PDF = "export_pdf"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_RESOLVED = "approval_resolved"
    AGENT_TOOL_CALL = "agent_tool_call"
    SESSION_STATUS = "session_status"
    ERROR = "error"


class TimelineStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class ArtifactKind(str, Enum):
    MARKDOWN = "markdown"
    DOCX = "docx"
    PDF = "pdf"


@dataclass(frozen=True)
class InputPaths:
    original_dir: str = "inputs/original"
    markdown_dir: str = "inputs/markdown"
    assets_dir: str = "inputs/assets"
    reports_dir: str = "inputs/reports"


@dataclass(frozen=True)
class ContextPaths:
    user_intent: str = "context/user_intent.md"
    doc_map: str = "context/doc_map.md"
    style_notes: str = "context/style_notes.md"
    structure_notes: str = "context/structure_notes.md"
    decision_log: str = "context/decision_log.md"
    open_questions: str = "context/open_questions.md"
    draft_summary: str = "context/draft_summary.md"


@dataclass(frozen=True)
class DraftPaths:
    outline: str = "draft/outline.md"
    current: str = "draft/draft.md"
    sections_dir: str = "draft/sections"


@dataclass(frozen=True)
class ReviewPaths:
    checklist_result: str = "reviews/checklist_result.md"
    self_review: str = "reviews/self_review.md"


@dataclass(frozen=True)
class LogPaths:
    agent_notes: str = "logs/agent_notes.md"


@dataclass(frozen=True)
class WorkspaceLayout:
    task_id: str
    root: str
    brief_path: str = "brief.md"
    inputs: InputPaths = field(default_factory=InputPaths)
    context: ContextPaths = field(default_factory=ContextPaths)
    draft: DraftPaths = field(default_factory=DraftPaths)
    versions_dir: str = "versions"
    reviews: ReviewPaths = field(default_factory=ReviewPaths)
    artifacts_dir: str = "artifacts"
    logs: LogPaths = field(default_factory=LogPaths)


@dataclass(frozen=True)
class ImportedResource:
    id: str
    scope: ResourceScope
    owner_id: str
    source_path: str
    markdown_path: str | None
    asset_dir: str | None
    conversion_report_path: str | None
    mime_type: str
    original_filename: str
    status: ResourceStatus
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ConversionReport:
    source_path: str
    markdown_path: str | None
    asset_dir: str | None
    engine: ConversionEngine
    status: ConversionStatus
    warnings: list[dict[str, Any]]
    features_detected: dict[str, int | None]
    created_at: str


@dataclass(frozen=True)
class SemanticTimelineEvent:
    id: str
    session_id: str
    task_id: str
    actor: TimelineActor
    kind: SemanticEventKind
    raw_event_id: str | None
    summary: str
    paths: list[str]
    status: TimelineStatus
    created_at: str


@dataclass(frozen=True)
class AcpEventEnvelope:
    id: str
    session_id: str
    sequence: int
    event_type: str
    payload: dict[str, Any]
    created_at: str
    projection: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DraftVersion:
    id: str
    task_id: str
    version: str
    source_path: str
    version_path: str
    summary: str
    created_by: str
    created_at: str


@dataclass(frozen=True)
class Artifact:
    id: str
    task_id: str
    draft_version_id: str | None
    kind: ArtifactKind
    path: str
    status: str
    created_at: str
