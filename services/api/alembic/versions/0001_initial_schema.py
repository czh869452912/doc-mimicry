"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

VALID_SESSION_STATUSES = (
    "pending",
    "running_context",
    "await_outline_approval",
    "running_draft",
    "draft_ready",
    "running_revision",
    "running_chat",
    "running_checklist",
    "running_export",
    "failed",
    "cancelled",
    "completed",
)


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("doc_type_id", sa.String(), nullable=False),
        sa.Column("brief", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.Text(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.String(),
            sa.CheckConstraint(
                f"status IN ({', '.join(repr(s) for s in VALID_SESSION_STATUSES)})",
                name="ck_sessions_status",
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.Text(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_sessions_task_id", "sessions", ["task_id"])

    op.create_table(
        "timeline_events",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=True),
            nullable=False,
        ),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_timeline_session_id", "timeline_events", ["session_id", "id"])

    op.create_table(
        "raw_runtime_events",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=True),
            nullable=False,
        ),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("runtime", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_raw_events_session_id", "raw_runtime_events", ["session_id"])


def downgrade() -> None:
    op.drop_index("idx_raw_events_session_id", table_name="raw_runtime_events")
    op.drop_table("raw_runtime_events")
    op.drop_index("idx_timeline_session_id", table_name="timeline_events")
    op.drop_table("timeline_events")
    op.drop_index("idx_sessions_task_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("tasks")
