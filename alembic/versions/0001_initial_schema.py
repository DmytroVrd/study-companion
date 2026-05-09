"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-07 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_telegram_id"), "users", ["telegram_id"], unique=True)

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=256), nullable=False),
        sa.Column("chroma_collection", sa.String(length=128), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chroma_collection"),
    )
    op.create_index(op.f("ix_documents_user_id"), "documents", ["user_id"], unique=False)

    op.create_table(
        "knowledge_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("topic", sa.String(length=256), nullable=False),
        sa.Column("easiness", sa.Float(), nullable=False),
        sa.Column("interval", sa.Integer(), nullable=False),
        sa.Column("repetitions", sa.Integer(), nullable=False),
        sa.Column("next_review", sa.DateTime(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "topic", name="uq_knowledge_user_topic"),
    )
    op.create_index(
        op.f("ix_knowledge_states_topic"), "knowledge_states", ["topic"], unique=False
    )
    op.create_index(
        op.f("ix_knowledge_states_user_id"), "knowledge_states", ["user_id"], unique=False
    )

    op.create_table(
        "quiz_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("topic", sa.String(length=256), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("user_answer", sa.Text(), nullable=False),
        sa.Column("correct", sa.Boolean(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_quiz_results_topic"), "quiz_results", ["topic"], unique=False)
    op.create_index(op.f("ix_quiz_results_user_id"), "quiz_results", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_quiz_results_user_id"), table_name="quiz_results")
    op.drop_index(op.f("ix_quiz_results_topic"), table_name="quiz_results")
    op.drop_table("quiz_results")
    op.drop_index(op.f("ix_knowledge_states_user_id"), table_name="knowledge_states")
    op.drop_index(op.f("ix_knowledge_states_topic"), table_name="knowledge_states")
    op.drop_table("knowledge_states")
    op.drop_index(op.f("ix_documents_user_id"), table_name="documents")
    op.drop_table("documents")
    op.drop_index(op.f("ix_users_telegram_id"), table_name="users")
    op.drop_table("users")
