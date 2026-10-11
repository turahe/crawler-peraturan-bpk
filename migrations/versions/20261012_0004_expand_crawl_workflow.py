"""expand crawl workflow tracking

Revision ID: 20261012_0004
Revises: 20261012_0003
Create Date: 2026-10-12 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261012_0004"
down_revision = "20261012_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("crawl_jobs") as batch_op:
        batch_op.alter_column(
            "regulation_id",
            existing_type=sa.BigInteger(),
            nullable=True,
        )
        batch_op.add_column(sa.Column("subject_id", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("stage", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_foreign_key(
            "fk_crawl_jobs_subject_id",
            "subjects",
            ["subject_id"],
            ["id"],
        )
        batch_op.create_index("ix_crawl_jobs_subject_id", ["subject_id"], unique=False)

    with op.batch_alter_table("document_metadata") as batch_op:
        batch_op.alter_column(
            "document_file_id",
            existing_type=sa.BigInteger(),
            nullable=True,
        )
        batch_op.add_column(sa.Column("regulation_id", sa.BigInteger(), nullable=True))
        batch_op.create_foreign_key(
            "fk_document_metadata_regulation_id",
            "regulations",
            ["regulation_id"],
            ["id"],
        )
        batch_op.create_index("ix_document_metadata_regulation_id", ["regulation_id"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("document_metadata") as batch_op:
        batch_op.drop_index("ix_document_metadata_regulation_id")
        batch_op.drop_constraint("fk_document_metadata_regulation_id", type_="foreignkey")
        batch_op.drop_column("regulation_id")
        batch_op.alter_column(
            "document_file_id",
            existing_type=sa.BigInteger(),
            nullable=False,
        )

    with op.batch_alter_table("crawl_jobs") as batch_op:
        batch_op.drop_index("ix_crawl_jobs_subject_id")
        batch_op.drop_constraint("fk_crawl_jobs_subject_id", type_="foreignkey")
        batch_op.drop_column("completed_at")
        batch_op.drop_column("stage")
        batch_op.drop_column("subject_id")
        batch_op.alter_column(
            "regulation_id",
            existing_type=sa.BigInteger(),
            nullable=False,
        )