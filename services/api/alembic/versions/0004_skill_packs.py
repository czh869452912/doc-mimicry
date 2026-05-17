"""add skill pack persistence model

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-17

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in set(inspector.get_table_names())


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _index_exists(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    inspector = sa.inspect(op.get_bind())
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    if not _table_exists("skill_packs"):
        op.create_table(
            "skill_packs",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("draft_status", sa.String(), nullable=False, server_default="draft"),
            sa.Column("latest_version_id", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _table_exists("skill_pack_resources"):
        op.create_table(
            "skill_pack_resources",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("pack_id", sa.String(), nullable=False),
            sa.Column("group", sa.String(), nullable=False),
            sa.Column("original_filename", sa.Text(), nullable=False),
            sa.Column("source_path", sa.Text(), nullable=False),
            sa.Column("markdown_path", sa.Text(), nullable=True),
            sa.Column("conversion_report_path", sa.Text(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["pack_id"], ["skill_packs.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _index_exists("skill_pack_resources", "idx_skill_pack_resources_pack"):
        op.create_index("idx_skill_pack_resources_pack", "skill_pack_resources", ["pack_id"])

    if not _table_exists("skill_pack_versions"):
        op.create_table(
            "skill_pack_versions",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("pack_id", sa.String(), nullable=False),
            sa.Column("version", sa.String(), nullable=False),
            sa.Column("snapshot_path", sa.Text(), nullable=False),
            sa.Column("manifest", postgresql.JSONB(), nullable=False),
            sa.Column("validation", postgresql.JSONB(), nullable=False),
            sa.Column("publish_note", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint("version <> ''", name="ck_skill_pack_versions_nonempty"),
            sa.ForeignKeyConstraint(["pack_id"], ["skill_packs.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _index_exists("skill_pack_versions", "idx_skill_pack_versions_pack"):
        op.create_index("idx_skill_pack_versions_pack", "skill_pack_versions", ["pack_id", "version"])

    if not _column_exists("tasks", "pack_version_id"):
        op.add_column("tasks", sa.Column("pack_version_id", sa.String(), nullable=True))
        op.create_foreign_key("fk_tasks_pack_version_id", "tasks", "skill_pack_versions", ["pack_version_id"], ["id"])

    if not _table_exists("skill_pack_artifact_revisions"):
        op.create_table(
            "skill_pack_artifact_revisions",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("pack_id", sa.String(), nullable=False),
            sa.Column("artifact_path", sa.Text(), nullable=False),
            sa.Column("content_sha256", sa.String(), nullable=False),
            sa.Column("source", sa.String(), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["pack_id"], ["skill_packs.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _index_exists("skill_pack_artifact_revisions", "idx_skill_pack_artifact_revisions_pack"):
        op.create_index(
            "idx_skill_pack_artifact_revisions_pack",
            "skill_pack_artifact_revisions",
            ["pack_id", "created_at"],
        )

    if not _table_exists("skill_creator_sessions"):
        op.create_table(
            "skill_creator_sessions",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("pack_id", sa.String(), nullable=False),
            sa.Column("session_scope", sa.String(), nullable=False, server_default="pack-management"),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("runtime", sa.String(), nullable=True),
            sa.Column("runtime_session_id", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["pack_id"], ["skill_packs.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _index_exists("skill_creator_sessions", "idx_skill_creator_sessions_pack"):
        op.create_index("idx_skill_creator_sessions_pack", "skill_creator_sessions", ["pack_id"])

    if not _table_exists("skill_creator_events"):
        op.create_table(
            "skill_creator_events",
            sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
            sa.Column("session_id", sa.String(), nullable=False),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("payload", postgresql.JSONB(), nullable=False),
            sa.Column("projection", postgresql.JSONB(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["session_id"], ["skill_creator_sessions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _index_exists("skill_creator_events", "idx_skill_creator_events_session"):
        op.create_index("idx_skill_creator_events_session", "skill_creator_events", ["session_id", "id"])


def downgrade() -> None:
    if _index_exists("skill_creator_events", "idx_skill_creator_events_session"):
        op.drop_index("idx_skill_creator_events_session", table_name="skill_creator_events")
    if _table_exists("skill_creator_events"):
        op.drop_table("skill_creator_events")
    if _index_exists("skill_creator_sessions", "idx_skill_creator_sessions_pack"):
        op.drop_index("idx_skill_creator_sessions_pack", table_name="skill_creator_sessions")
    if _table_exists("skill_creator_sessions"):
        op.drop_table("skill_creator_sessions")
    if _index_exists("skill_pack_artifact_revisions", "idx_skill_pack_artifact_revisions_pack"):
        op.drop_index("idx_skill_pack_artifact_revisions_pack", table_name="skill_pack_artifact_revisions")
    if _table_exists("skill_pack_artifact_revisions"):
        op.drop_table("skill_pack_artifact_revisions")
    if _column_exists("tasks", "pack_version_id"):
        op.drop_column("tasks", "pack_version_id")
    if _index_exists("skill_pack_versions", "idx_skill_pack_versions_pack"):
        op.drop_index("idx_skill_pack_versions_pack", table_name="skill_pack_versions")
    if _table_exists("skill_pack_versions"):
        op.drop_table("skill_pack_versions")
    if _index_exists("skill_pack_resources", "idx_skill_pack_resources_pack"):
        op.drop_index("idx_skill_pack_resources_pack", table_name="skill_pack_resources")
    if _table_exists("skill_pack_resources"):
        op.drop_table("skill_pack_resources")
    if _table_exists("skill_packs"):
        op.drop_table("skill_packs")
