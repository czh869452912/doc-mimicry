from __future__ import annotations

import os

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.sql import func

_DATABASE_URL_ENV = "DATABASE_URL"
_DEFAULT_DATABASE_URL = "postgresql+psycopg2://docagent:docagent@localhost:5432/docagent"

VALID_SESSION_STATUSES = (
    "idle",
    "pending",
    "running_context",
    "await_outline_approval",
    "running_draft",
    "draft_ready",
    "running_revision",
    "running_chat",
    "running_checklist",
    "running_export",
    "paused",
    "failed",
    "cancelled",
    "completed",
)


class Base(DeclarativeBase):
    pass


class TaskRow(Base):
    __tablename__ = "tasks"
    id = Column(String, primary_key=True)
    doc_type_id = Column(String, nullable=False)
    pack_version_id = Column(String, ForeignKey("skill_pack_versions.id"), nullable=True)
    brief = Column(Text, nullable=False)
    title = Column(Text)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class SessionRow(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=False)
    status = Column(
        String,
        CheckConstraint(f"status IN ({', '.join(repr(s) for s in VALID_SESSION_STATUSES)})"),
        nullable=False,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    runtime = Column(String, nullable=True)
    runtime_session_id = Column(String, nullable=True)
    celery_task_id = Column(String, nullable=True)

    __table_args__ = (Index("idx_sessions_task_id", "task_id"),)


class TimelineEventRow(Base):
    __tablename__ = "timeline_events"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    event_type = Column(String, nullable=False)
    payload = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (Index("idx_timeline_session_id", "session_id", "id"),)


class AcpEventRow(Base):
    __tablename__ = "acp_events"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    event_type = Column(String, nullable=False)
    payload = Column(JSONB, nullable=False)
    projection = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (Index("idx_acp_events_session_id", "session_id", "id"),)


class RawRuntimeEventRow(Base):
    __tablename__ = "raw_runtime_events"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    runtime = Column(String, nullable=False)
    payload = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (Index("idx_raw_events_session_id", "session_id"),)


class SkillPackRow(Base):
    __tablename__ = "skill_packs"
    id = Column(String, primary_key=True)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=False, default="")
    draft_status = Column(String, nullable=False, default="draft")
    latest_version_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class SkillPackResourceRow(Base):
    __tablename__ = "skill_pack_resources"
    id = Column(String, primary_key=True)
    pack_id = Column(String, ForeignKey("skill_packs.id"), nullable=False)
    group = Column(String, nullable=False)
    original_filename = Column(Text, nullable=False)
    source_path = Column(Text, nullable=False)
    markdown_path = Column(Text)
    conversion_report_path = Column(Text, nullable=False)
    status = Column(String, nullable=False)
    summary = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (Index("idx_skill_pack_resources_pack", "pack_id"),)


class SkillPackVersionRow(Base):
    __tablename__ = "skill_pack_versions"
    id = Column(String, primary_key=True)
    pack_id = Column(String, ForeignKey("skill_packs.id"), nullable=False)
    version = Column(String, nullable=False)
    snapshot_path = Column(Text, nullable=False)
    manifest = Column(JSONB, nullable=False)
    validation = Column(JSONB, nullable=False)
    publish_note = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_skill_pack_versions_pack", "pack_id", "version"),
        UniqueConstraint("pack_id", "version", name="uq_skill_pack_versions_pack_version"),
        CheckConstraint("version <> ''", name="ck_skill_pack_versions_nonempty"),
    )


class SkillPackArtifactRevisionRow(Base):
    __tablename__ = "skill_pack_artifact_revisions"
    id = Column(String, primary_key=True)
    pack_id = Column(String, ForeignKey("skill_packs.id"), nullable=False)
    artifact_path = Column(Text, nullable=False)
    content_sha256 = Column(String, nullable=False)
    source = Column(String, nullable=False)
    summary = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (Index("idx_skill_pack_artifact_revisions_pack", "pack_id", "created_at"),)


class SkillCreatorSessionRow(Base):
    __tablename__ = "skill_creator_sessions"
    id = Column(String, primary_key=True)
    pack_id = Column(String, ForeignKey("skill_packs.id"), nullable=False)
    session_scope = Column(String, nullable=False, default="pack-management")
    status = Column(String, nullable=False)
    runtime = Column(String)
    runtime_session_id = Column(String)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (Index("idx_skill_creator_sessions_pack", "pack_id"),)


class SkillCreatorEventRow(Base):
    __tablename__ = "skill_creator_events"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("skill_creator_sessions.id"), nullable=False)
    event_type = Column(String, nullable=False)
    payload = Column(JSONB, nullable=False)
    projection = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (Index("idx_skill_creator_events_session", "session_id", "id"),)


def get_database_url() -> str:
    return os.environ.get(_DATABASE_URL_ENV, _DEFAULT_DATABASE_URL)


def create_db_engine(database_url: str | None = None):
    url = database_url or get_database_url()
    return create_engine(
        url,
        pool_size=int(os.environ.get("DB_POOL_SIZE", "5")),
        max_overflow=int(os.environ.get("DB_MAX_OVERFLOW", "10")),
        pool_timeout=30,
        pool_recycle=1800,
    )


def create_session_factory(engine) -> sessionmaker:
    return sessionmaker(bind=engine)


def create_tables(engine) -> None:
    Base.metadata.create_all(engine)
