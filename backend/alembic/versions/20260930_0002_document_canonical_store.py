"""Canonical document store columns on document_memory

Revision ID: 20260930_0002
Revises: 20260827_0001
Create Date: 2026-09-30 00:00:00

Adds the columns that make the stored original the source of truth for a document:
storage_path (relative to VAULT_FILES_DIR), doc_type, parser_version, indexed_at.
Purely additive and nullable, so it is safe on populated databases; downgrade drops only these columns
(never any stored original file).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260930_0002"
down_revision: Union[str, None] = "20260827_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = (
    ("storage_path", sa.String(length=512)),
    ("doc_type", sa.String(length=32)),
    ("parser_version", sa.String(length=64)),
    ("indexed_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("document_memory")}
    with op.batch_alter_table("document_memory") as batch_op:
        for name, type_ in _COLUMNS:
            if name not in existing:  # the runtime additive path may have created it already
                batch_op.add_column(sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("document_memory")}
    with op.batch_alter_table("document_memory") as batch_op:
        for name, _ in _COLUMNS:
            if name in existing:
                batch_op.drop_column(name)
