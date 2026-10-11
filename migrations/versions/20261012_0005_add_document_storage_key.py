"""add document storage key

Revision ID: 20261012_0005
Revises: 20261012_0004
Create Date: 2026-10-12 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261012_0005"
down_revision = "20261012_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("document_files")}
    if "storage_key" not in columns:
        op.add_column("document_files", sa.Column("storage_key", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("document_files")}
    if "storage_key" in columns:
        op.drop_column("document_files", "storage_key")