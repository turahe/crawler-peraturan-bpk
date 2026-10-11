"""add document file storage metadata

Revision ID: 20261012_0002
Revises: 20261010_0001
Create Date: 2026-10-12 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261012_0002"
down_revision = "20261010_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("document_files")}

    new_columns = (
        sa.Column("original_file_name", sa.String(), nullable=True),
        sa.Column("file_extension", sa.String(length=32), nullable=True),
        sa.Column("storage_key", sa.Text(), nullable=True),
        sa.Column("storage_path", sa.Text(), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=True),
    )
    for column in new_columns:
        if column.name not in existing_columns:
            op.add_column("document_files", column)

    if "regulation_id" in existing_columns:
        regulation_id = next(column for column in inspector.get_columns("document_files") if column["name"] == "regulation_id")
        if not regulation_id["nullable"]:
            with op.batch_alter_table("document_files") as batch_op:
                batch_op.alter_column(
                    "regulation_id",
                    existing_type=regulation_id["type"],
                    nullable=True,
                )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("document_files")}

    for column_name in ("downloaded_at", "storage_path", "storage_key", "file_extension", "original_file_name"):
        if column_name in existing_columns:
            op.drop_column("document_files", column_name)

    regulation_id = next(
        (column for column in inspector.get_columns("document_files") if column["name"] == "regulation_id"),
        None,
    )
    if regulation_id is not None and regulation_id["nullable"]:
        with op.batch_alter_table("document_files") as batch_op:
            batch_op.alter_column(
                "regulation_id",
                existing_type=regulation_id["type"],
                nullable=False,
            )