"""Add lightweight graph tables and richer query observability

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "query_logs",
        sa.Column("query_mode", sa.String(length=32), nullable=False, server_default="hybrid"),
    )
    op.add_column(
        "query_logs",
        sa.Column("retrieval_trace", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
    )
    op.add_column(
        "query_logs",
        sa.Column("eval_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
    )

    op.create_table(
        "entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False, server_default="named_entity"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("mention_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_entities_project_id", "entities", ["project_id"])
    op.create_index("ix_entities_normalized_name", "entities", ["normalized_name"])

    op.create_table(
        "relations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relation_type", sa.String(length=64), nullable=False, server_default="related_to"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("weight", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_relations_project_id", "relations", ["project_id"])
    op.create_index("ix_relations_source_entity_id", "relations", ["source_entity_id"])
    op.create_index("ix_relations_target_entity_id", "relations", ["target_entity_id"])

    op.create_table(
        "document_entities",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mention_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("chunk_indices", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("document_id", "entity_id"),
    )

    op.create_table(
        "document_relations",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("relations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mention_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("chunk_indices", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("document_id", "relation_id"),
    )


def downgrade() -> None:
    op.drop_table("document_relations")
    op.drop_table("document_entities")
    op.drop_index("ix_relations_target_entity_id", table_name="relations")
    op.drop_index("ix_relations_source_entity_id", table_name="relations")
    op.drop_index("ix_relations_project_id", table_name="relations")
    op.drop_table("relations")
    op.drop_index("ix_entities_normalized_name", table_name="entities")
    op.drop_index("ix_entities_project_id", table_name="entities")
    op.drop_table("entities")
    op.drop_column("query_logs", "eval_payload")
    op.drop_column("query_logs", "retrieval_trace")
    op.drop_column("query_logs", "query_mode")
