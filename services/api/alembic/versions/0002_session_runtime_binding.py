"""add session runtime binding columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-12

"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


RUNTIME_COLUMNS = [
    sa.Column("runtime", sa.String(), nullable=True),
    sa.Column("runtime_session_id", sa.String(), nullable=True),
    sa.Column("celery_task_id", sa.String(), nullable=True),
]


def _session_column_names() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns("sessions")}


def upgrade() -> None:
    existing_columns = _session_column_names()
    for column in RUNTIME_COLUMNS:
        if column.name not in existing_columns:
            op.add_column("sessions", column)


def downgrade() -> None:
    existing_columns = _session_column_names()
    for column_name in ("celery_task_id", "runtime_session_id", "runtime"):
        if column_name in existing_columns:
            op.drop_column("sessions", column_name)
