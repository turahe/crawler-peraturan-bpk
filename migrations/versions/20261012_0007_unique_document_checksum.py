"""make document checksum an idempotency key

Revision ID: 20261012_0007
Revises: 20261012_0006
Create Date: 2026-10-12 00:00:00
"""

from __future__ import annotations

from alembic import op


revision = "20261012_0007"
down_revision = "20261012_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Preserve existing rows while retaining one canonical idempotency key for
    # each content hash. New downloads will reuse that canonical row.
    op.execute(
        """
        UPDATE document_files
        SET checksum_sha256 = NULL
        WHERE id IN (
            SELECT id
            FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY checksum_sha256 ORDER BY id
                       ) AS checksum_rank
                FROM document_files
                WHERE checksum_sha256 IS NOT NULL
            ) ranked
            WHERE checksum_rank > 1
        )
        """
    )
    op.create_index(
        "uq_document_files_checksum_sha256",
        "document_files",
        ["checksum_sha256"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_document_files_checksum_sha256", table_name="document_files")
