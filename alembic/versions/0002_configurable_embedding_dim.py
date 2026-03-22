"""Change embedding dimension to 384 for sentence_transformer support

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-22

Switches from vector(1536) (OpenAI text-embedding-3-small) to vector(384)
(SentenceTransformer all-MiniLM-L6-v2) so the system works without API keys.
Existing chunks with 1536-dim embeddings are deleted before the ALTER since
dimensions are incompatible.

To use OpenAI instead: set EMBEDDING_PROVIDER=openai and EMBEDDING_DIM=1536
in your .env, then write a new migration to ALTER the column back to vector(1536).
"""

from alembic import op


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove any existing chunks — their embeddings are the wrong dimension.
    op.execute("DELETE FROM chunks")
    op.execute("ALTER TABLE chunks ALTER COLUMN embedding TYPE vector(384)")


def downgrade() -> None:
    op.execute("DELETE FROM chunks")
    op.execute("ALTER TABLE chunks ALTER COLUMN embedding TYPE vector(1536)")
