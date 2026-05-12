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


def upgrade() -> None:
    op.add_column("sessions", sa.Column("runtime", sa.String(), nullable=True))
    op.add_column("sessions", sa.Column("runtime_session_id", sa.String(), nullable=True))
    op.add_column("sessions", sa.Column("celery_task_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("sessions", "celery_task_id")
    op.drop_column("sessions", "runtime_session_id")
    op.drop_column("sessions", "runtime")
