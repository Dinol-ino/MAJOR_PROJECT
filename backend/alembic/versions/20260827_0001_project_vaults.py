"""Phase 01 Project Vaults, Persistent Memory and Ingestion Lifecycle

Revision ID: 20260827_0001
Revises: 20260827_0000
Create Date: 2026-08-27 01:00:00

"""
from typing import Sequence, Union
import uuid
from datetime import datetime
from alembic import op
import sqlalchemy as sa

revision: str = "20260827_0001"
down_revision: Union[str, None] = "20260827_0000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. project_vaults table
    op.create_table(
        "project_vaults",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("vault_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_project_vaults_user_id", "project_vaults", ["user_id"])

    # 2. Add project_vault_id to conversations
    with op.batch_alter_table("conversations") as batch_op:
        batch_op.add_column(sa.Column("project_vault_id", sa.String(length=64), nullable=True))
        batch_op.create_index("ix_conversations_project_vault_id", ["project_vault_id"])

    # 3. Add fields to messages
    with op.batch_alter_table("messages") as batch_op:
        batch_op.add_column(sa.Column("citations_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("reasoning_trace", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("model_used", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("runtime_used", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("token_count", sa.Integer(), nullable=True))

    # 4. Add fields to document_memory
    with op.batch_alter_table("document_memory") as batch_op:
        batch_op.add_column(sa.Column("project_vault_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("file_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("vector_ns", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("ingest_status", sa.String(length=32), nullable=False, server_default="ready"))
        batch_op.add_column(sa.Column("ingest_error", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("ingest_progress", sa.Integer(), nullable=False, server_default="100"))
        batch_op.create_index("ix_document_memory_project_vault_id", ["project_vault_id"])
        batch_op.create_index("ix_document_memory_file_hash", ["file_hash"])

    # 5. document_pages table
    op.create_table(
        "document_pages",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("doc_id", sa.String(length=64), sa.ForeignKey("document_memory.doc_id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_no", sa.Integer(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_document_pages_doc_id", "document_pages", ["doc_id"])


def downgrade() -> None:
    op.drop_table("document_pages")
    with op.batch_alter_table("document_memory") as batch_op:
        batch_op.drop_index("ix_document_memory_file_hash")
        batch_op.drop_index("ix_document_memory_project_vault_id")
        batch_op.drop_column("ingest_progress")
        batch_op.drop_column("ingest_error")
        batch_op.drop_column("ingest_status")
        batch_op.drop_column("vector_ns")
        batch_op.drop_column("file_hash")
        batch_op.drop_column("project_vault_id")

    with op.batch_alter_table("messages") as batch_op:
        batch_op.drop_column("token_count")
        batch_op.drop_column("runtime_used")
        batch_op.drop_column("model_used")
        batch_op.drop_column("reasoning_trace")
        batch_op.drop_column("citations_json")

    with op.batch_alter_table("conversations") as batch_op:
        batch_op.drop_index("ix_conversations_project_vault_id")
        batch_op.drop_column("project_vault_id")

    op.drop_table("project_vaults")
