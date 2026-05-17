"""add unique skill pack version numbers

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-17

"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

CONSTRAINT_NAME = "uq_skill_pack_versions_pack_version"


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in set(inspector.get_table_names())


def _unique_constraint_exists(table_name: str, constraint_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    inspector = sa.inspect(op.get_bind())
    return constraint_name in {
        constraint["name"] for constraint in inspector.get_unique_constraints(table_name)
    }


def upgrade() -> None:
    if not _unique_constraint_exists("skill_pack_versions", CONSTRAINT_NAME):
        op.create_unique_constraint(
            CONSTRAINT_NAME,
            "skill_pack_versions",
            ["pack_id", "version"],
        )


def downgrade() -> None:
    if _unique_constraint_exists("skill_pack_versions", CONSTRAINT_NAME):
        op.drop_constraint(CONSTRAINT_NAME, "skill_pack_versions", type_="unique")
