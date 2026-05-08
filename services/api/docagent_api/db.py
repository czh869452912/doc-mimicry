from __future__ import annotations

import os

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Index,
    String,
    Text,
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
    brief = Column(Text, nullable=False)
    title = Column(Text)
    description = Column(Text)
    created_at = Column(Text, nullable=False, server_default=func.now())
    updated_at = Column(Text, nullable=False, server_default=func.now(), onupdate=func.now())


class SessionRow(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True)
    task_id = Column(String, nullable=False)
    status = Column(
        String,
        CheckConstraint(f"status IN ({', '.join(repr(s) for s in VALID_SESSION_STATUSES)})"),
        nullable=False,
    )
    created_at = Column(Text, nullable=False, server_default=func.now())
    updated_at = Column(Text, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (Index("idx_sessions_task_id", "task_id"),)


class TimelineEventRow(Base):
    __tablename__ = "timeline_events"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    payload = Column(JSONB, nullable=False)
    created_at = Column(Text, nullable=False, server_default=func.now())

    __table_args__ = (Index("idx_timeline_session_id", "session_id", "id"),)


class RawRuntimeEventRow(Base):
    __tablename__ = "raw_runtime_events"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False)
    runtime = Column(String, nullable=False)
    payload = Column(JSONB, nullable=False)
    created_at = Column(Text, nullable=False, server_default=func.now())

    __table_args__ = (Index("idx_raw_events_session_id", "session_id"),)


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
