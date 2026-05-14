"""Add platform field and index.

Demonstrates backward-compatible schema evolution: the column is nullable
so older records (platform=NULL) keep working. The CHECK constraint restricts
values for new writes without touching existing rows.

Revision ID: 002
Create Date: 2025-01-02
"""

import sqlalchemy as sa
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

VALID_PLATFORMS = ("instagram", "tiktok", "youtube", "other")


def upgrade() -> None:
    # Column already exists in 001 (nullable), so this migration only adds
    # the CHECK constraint and an index for per-platform queries.
    op.create_check_constraint(
        "ck_publications_platform",
        "publications",
        sa.text(f"platform IS NULL OR platform IN {VALID_PLATFORMS!r}"),
    )
    op.create_index("ix_publications_platform", "publications", ["platform"])


def downgrade() -> None:
    op.drop_index("ix_publications_platform", table_name="publications")
    op.drop_constraint("ck_publications_platform", "publications", type_="check")
