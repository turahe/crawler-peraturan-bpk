"""add crawler lookup indexes

Revision ID: 20261012_0006
Revises: 20261012_0005
Create Date: 2026-10-12 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261012_0006"
down_revision = "20261012_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_subjects_source_theme_id", "subjects", ["source_theme_id"], unique=True)
    op.create_index("ix_regulations_source_id", "regulations", ["source_id"], unique=True)
    op.create_index("ix_regulations_detail_url", "regulations", ["detail_url"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_regulations_detail_url", table_name="regulations")
    op.drop_index("ix_regulations_source_id", table_name="regulations")
    op.drop_index("ix_subjects_source_theme_id", table_name="subjects")