"""Phase 02 Persistence & PostgreSQL schema

Revision ID: 20260827_0000
Revises: 
Create Date: 2026-08-27 00:00:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "20260827_0000"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. conversations table
    op.create_table(
        "conversations",
        sa.Column("conversation_id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.create_index("ix_conversations_conversation_id", "conversations", ["conversation_id"])

    # 2. messages table
    op.create_table(
        "messages",
        sa.Column("message_id", sa.String(length=64), primary_key=True),
        sa.Column("conversation_id", sa.String(length=64), sa.ForeignKey("conversations.conversation_id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=True),
        sa.Column("blocked_by", sa.String(length=64), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_message_id", "messages", ["message_id"])

    # 3. semantic_memory table
    op.create_table(
        "semantic_memory",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_semantic_memory_user_id", "semantic_memory", ["user_id"])
    op.create_index("ix_semantic_memory_category", "semantic_memory", ["category"])
    op.create_index("ix_semantic_user_cat_key", "semantic_memory", ["user_id", "category", "key"])

    # 4. document_memory table
    op.create_table(
        "document_memory",
        sa.Column("doc_id", sa.String(length=64), primary_key=True),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_document_memory_session_id", "document_memory", ["session_id"])

    # 5. research_sessions table
    op.create_table(
        "research_sessions",
        sa.Column("session_id", sa.String(length=64), primary_key=True),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("findings", sa.Text(), nullable=True),
        sa.Column("sources", sa.JSON(), nullable=True),
        sa.Column("citations", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 6. audit_events table
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ts", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("layer", sa.String(length=64), nullable=True),
        sa.Column("injection_score", sa.Float(), nullable=True),
        sa.Column("retrieval_hits", sa.Integer(), nullable=True),
        sa.Column("citations_used", sa.Integer(), nullable=True),
        sa.Column("validation_pass_fail", sa.String(length=32), nullable=True),
        sa.Column("model_tier_used", sa.String(length=64), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("hash", sa.String(length=64), nullable=False),
        sa.Column("prev_hash", sa.String(length=64), nullable=False),
    )
    op.create_index("ix_audit_events_action", "audit_events", ["action"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("research_sessions")
    op.drop_table("document_memory")
    op.drop_table("semantic_memory")
    op.drop_table("messages")
    op.drop_table("conversations")
