"""study contexts

Revision ID: 0003_study_contexts
Revises: 0002_telegram_id_bigint
Create Date: 2026-05-07 00:00:02.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_study_contexts"
down_revision: str | None = "0002_telegram_id_bigint"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "study_contexts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_study_contexts_is_active"), "study_contexts", ["is_active"])
    op.create_index(op.f("ix_study_contexts_user_id"), "study_contexts", ["user_id"])

    op.add_column("documents", sa.Column("context_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_documents_context_id"), "documents", ["context_id"])
    op.create_foreign_key(
        "fk_documents_context_id_study_contexts",
        "documents",
        "study_contexts",
        ["context_id"],
        ["id"],
    )

    op.add_column("knowledge_states", sa.Column("context_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_knowledge_states_context_id"), "knowledge_states", ["context_id"])
    op.create_foreign_key(
        "fk_knowledge_states_context_id_study_contexts",
        "knowledge_states",
        "study_contexts",
        ["context_id"],
        ["id"],
    )

    op.add_column("quiz_results", sa.Column("context_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_quiz_results_context_id"), "quiz_results", ["context_id"])
    op.create_foreign_key(
        "fk_quiz_results_context_id_study_contexts",
        "quiz_results",
        "study_contexts",
        ["context_id"],
        ["id"],
    )

    op.execute(
        """
        INSERT INTO study_contexts (user_id, title, is_active, created_at)
        SELECT id, 'Imported context', true, CURRENT_TIMESTAMP
        FROM users
        WHERE EXISTS (
            SELECT 1 FROM documents WHERE documents.user_id = users.id
            UNION
            SELECT 1 FROM knowledge_states WHERE knowledge_states.user_id = users.id
            UNION
            SELECT 1 FROM quiz_results WHERE quiz_results.user_id = users.id
        )
        """
    )
    op.execute(
        """
        UPDATE documents
        SET context_id = study_contexts.id
        FROM study_contexts
        WHERE documents.user_id = study_contexts.user_id
          AND study_contexts.title = 'Imported context'
        """
    )
    op.execute(
        """
        UPDATE knowledge_states
        SET context_id = study_contexts.id
        FROM study_contexts
        WHERE knowledge_states.user_id = study_contexts.user_id
          AND study_contexts.title = 'Imported context'
        """
    )
    op.execute(
        """
        UPDATE quiz_results
        SET context_id = study_contexts.id
        FROM study_contexts
        WHERE quiz_results.user_id = study_contexts.user_id
          AND study_contexts.title = 'Imported context'
        """
    )

    op.drop_constraint("uq_knowledge_user_topic", "knowledge_states", type_="unique")
    op.create_unique_constraint(
        "uq_knowledge_context_topic", "knowledge_states", ["context_id", "topic"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_knowledge_context_topic", "knowledge_states", type_="unique")
    op.create_unique_constraint(
        "uq_knowledge_user_topic", "knowledge_states", ["user_id", "topic"]
    )

    op.drop_constraint(
        "fk_quiz_results_context_id_study_contexts", "quiz_results", type_="foreignkey"
    )
    op.drop_index(op.f("ix_quiz_results_context_id"), table_name="quiz_results")
    op.drop_column("quiz_results", "context_id")

    op.drop_constraint(
        "fk_knowledge_states_context_id_study_contexts",
        "knowledge_states",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_knowledge_states_context_id"), table_name="knowledge_states")
    op.drop_column("knowledge_states", "context_id")

    op.drop_constraint(
        "fk_documents_context_id_study_contexts", "documents", type_="foreignkey"
    )
    op.drop_index(op.f("ix_documents_context_id"), table_name="documents")
    op.drop_column("documents", "context_id")

    op.drop_index(op.f("ix_study_contexts_user_id"), table_name="study_contexts")
    op.drop_index(op.f("ix_study_contexts_is_active"), table_name="study_contexts")
    op.drop_table("study_contexts")
