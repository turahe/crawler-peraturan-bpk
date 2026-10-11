"""create regulation schema

Revision ID: 20261010_0001
Revises: 
Create Date: 2026-10-10 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20261010_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subjects",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.UUID(), nullable=False),
        sa.Column("source_theme_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("uuid", name="uq_subjects_uuid"),
        sa.UniqueConstraint("source_theme_id", name="uq_subjects_source_theme_id"),
    )
    op.create_index(op.f("ix_subjects_uuid"), "subjects", ["uuid"], unique=True)

    op.create_table(
        "regulations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("document_number", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("detail_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("uuid", name="uq_regulations_uuid"),
        sa.UniqueConstraint("source_id", name="uq_regulations_source_id"),
        sa.UniqueConstraint("detail_url", name="uq_regulations_detail_url"),
    )
    op.create_index(op.f("ix_regulations_uuid"), "regulations", ["uuid"], unique=True)

    op.create_table(
        "regulation_subjects",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.UUID(), nullable=False),
        sa.Column("regulation_id", sa.BigInteger(), sa.ForeignKey("regulations.id"), nullable=False),
        sa.Column("subject_id", sa.BigInteger(), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("uuid", name="uq_regulation_subjects_uuid"),
        sa.UniqueConstraint("regulation_id", "subject_id", name="uq_regulation_subjects_regulation_subject"),
    )
    op.create_index(op.f("ix_regulation_subjects_uuid"), "regulation_subjects", ["uuid"], unique=True)
    op.create_index(op.f("ix_regulation_subjects_regulation_id"), "regulation_subjects", ["regulation_id"], unique=False)
    op.create_index(op.f("ix_regulation_subjects_subject_id"), "regulation_subjects", ["subject_id"], unique=False)

    op.create_table(
        "crawl_jobs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.UUID(), nullable=False),
        sa.Column("regulation_id", sa.BigInteger(), sa.ForeignKey("regulations.id"), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("uuid", name="uq_crawl_jobs_uuid"),
    )
    op.create_index(op.f("ix_crawl_jobs_uuid"), "crawl_jobs", ["uuid"], unique=True)
    op.create_index(op.f("ix_crawl_jobs_regulation_id"), "crawl_jobs", ["regulation_id"], unique=False)

    op.create_table(
        "document_files",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.UUID(), nullable=False),
        sa.Column("regulation_id", sa.BigInteger(), sa.ForeignKey("regulations.id"), nullable=False),
        sa.Column("hash", sa.String(), nullable=True),
        sa.Column("file_name", sa.String(), nullable=True),
        sa.Column("disk", sa.String(), nullable=True),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("size", sa.BigInteger(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("uuid", name="uq_document_files_uuid"),
    )
    op.create_index(op.f("ix_document_files_uuid"), "document_files", ["uuid"], unique=True)
    op.create_index(op.f("ix_document_files_regulation_id"), "document_files", ["regulation_id"], unique=False)

    op.create_table(
        "document_metadata",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("document_file_id", sa.BigInteger(), sa.ForeignKey("document_files.id"), nullable=False, unique=True),
        sa.Column("document_type", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("author", sa.String(), nullable=True),
        sa.Column("number", sa.String(), nullable=True),
        sa.Column("form", sa.String(), nullable=True),
        sa.Column("short_form", sa.String(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("place_enactment", sa.String(), nullable=True),
        sa.Column("date_enacted", sa.Date(), nullable=True),
        sa.Column("date_promulgated", sa.Date(), nullable=True),
        sa.Column("date_effective", sa.Date(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("subject", sa.String(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("field", sa.String(), nullable=True),
        sa.Column("alias", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index(op.f("ix_document_metadata_document_file_id"), "document_metadata", ["document_file_id"], unique=True)

    op.create_table(
        "document_pages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.UUID(), nullable=False),
        sa.Column("document_file_id", sa.BigInteger(), sa.ForeignKey("document_files.id"), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("uuid", name="uq_document_pages_uuid"),
        sa.UniqueConstraint("document_file_id", "page_number", name="uq_document_pages_document_file_page_number"),
    )
    op.create_index(op.f("ix_document_pages_uuid"), "document_pages", ["uuid"], unique=True)
    op.create_index(op.f("ix_document_pages_document_file_id"), "document_pages", ["document_file_id"], unique=False)

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.UUID(), nullable=False),
        sa.Column("document_page_id", sa.BigInteger(), sa.ForeignKey("document_pages.id"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("uuid", name="uq_document_chunks_uuid"),
    )
    op.create_index(op.f("ix_document_chunks_uuid"), "document_chunks", ["uuid"], unique=True)
    op.create_index(op.f("ix_document_chunks_document_page_id"), "document_chunks", ["document_page_id"], unique=False)

    op.create_table(
        "regulation_relations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.UUID(), nullable=False),
        sa.Column("source_regulation_id", sa.BigInteger(), sa.ForeignKey("regulations.id"), nullable=False),
        sa.Column("target_regulation_id", sa.BigInteger(), sa.ForeignKey("regulations.id"), nullable=False),
        sa.Column("relation_type", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("uuid", name="uq_regulation_relations_uuid"),
        sa.UniqueConstraint("source_regulation_id", "target_regulation_id", "relation_type", name="uq_regulation_relations_source_target_type"),
    )
    op.create_index(op.f("ix_regulation_relations_uuid"), "regulation_relations", ["uuid"], unique=True)
    op.create_index(op.f("ix_regulation_relations_source_regulation_id"), "regulation_relations", ["source_regulation_id"], unique=False)
    op.create_index(op.f("ix_regulation_relations_target_regulation_id"), "regulation_relations", ["target_regulation_id"], unique=False)


def downgrade() -> None:
    op.drop_table("regulation_relations")
    op.drop_table("document_chunks")
    op.drop_table("document_pages")
    op.drop_table("document_metadata")
    op.drop_table("document_files")
    op.drop_table("crawl_jobs")
    op.drop_table("regulation_subjects")
    op.drop_table("regulations")
    op.drop_table("subjects")
