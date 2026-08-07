"""stage1 session owner isolation

Revision ID: 20260803_1700
Revises: 195cfb0e84e1
Create Date: 2026-08-03 17:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260803_1700"
down_revision = "195cfb0e84e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_sessions_owner_user_id_users",
        "sessions",
        "users",
        ["owner_user_id"],
        ["id"],
    )
    op.create_index("ix_sessions_owner_user_id", "sessions", ["owner_user_id"])


def downgrade() -> None:
    op.drop_index("ix_sessions_owner_user_id", table_name="sessions")
    op.drop_constraint("fk_sessions_owner_user_id_users", "sessions", type_="foreignkey")
    op.drop_column("sessions", "owner_user_id")
