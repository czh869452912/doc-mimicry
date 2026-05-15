"""add ACP event store

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

ACP_EVENTS_TABLE = "acp_events"
ACP_EVENTS_INDEX = "idx_acp_events_session_id"


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in set(inspector.get_table_names())


def _index_exists(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    inspector = sa.inspect(op.get_bind())
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    table_exists = _table_exists(ACP_EVENTS_TABLE)
    if not table_exists:
        op.create_table(
            ACP_EVENTS_TABLE,
            sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
            sa.Column("session_id", sa.String(), nullable=False),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("payload", postgresql.JSONB(), nullable=False),
            sa.Column("projection", postgresql.JSONB(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _index_exists(ACP_EVENTS_TABLE, ACP_EVENTS_INDEX):
        op.create_index(ACP_EVENTS_INDEX, ACP_EVENTS_TABLE, ["session_id", "id"])


def downgrade() -> None:
    if _index_exists(ACP_EVENTS_TABLE, ACP_EVENTS_INDEX):
        op.drop_index(ACP_EVENTS_INDEX, table_name=ACP_EVENTS_TABLE)
    if _table_exists(ACP_EVENTS_TABLE):
        op.drop_table(ACP_EVENTS_TABLE)
