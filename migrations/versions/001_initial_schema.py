"""Initial publications schema.

Revision ID: 001
Create Date: 2025-01-01
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "publications",
        sa.Column("publication_id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("publication_url", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("author_name", sa.String(), nullable=False),
        sa.Column("author_id", UUID(as_uuid=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("media_url", sa.String(), nullable=False),
        sa.Column("metrics", JSONB(), nullable=False),
        sa.Column("engagement_rate", sa.Float(), nullable=False),
        sa.Column("platform", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("publication_id"),
        sa.UniqueConstraint("publication_url", name="uq_publications_url"),
    )
    op.create_index("ix_publications_author_id", "publications", ["author_id"])
    op.create_index("ix_publications_published_at", "publications", ["published_at"])
    op.create_index("ix_publications_created_at", "publications", ["created_at"])
    op.create_index("ix_publications_deleted_at", "publications", ["deleted_at"], postgresql_where=sa.text("deleted_at IS NULL"))


def downgrade() -> None:
    op.drop_table("publications")
