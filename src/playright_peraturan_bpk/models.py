from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    UUID,
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


PRIMARY_KEY_TYPE = BigInteger().with_variant(Integer, "sqlite")


class Subject(Base):
    __tablename__ = "subjects"
    __table_args__ = (
        UniqueConstraint("uuid", name="uq_subjects_uuid"),
        UniqueConstraint("source_theme_id", name="uq_subjects_source_theme_id"),
    )

    id: Mapped[int] = mapped_column(PRIMARY_KEY_TYPE, primary_key=True, autoincrement=True)
    uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        default=uuid.uuid4,
        index=True,
    )
    source_theme_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    regulations: Mapped[list["Regulation"]] = relationship(
        secondary="regulation_subjects",
        back_populates="subjects",
    )
    crawl_jobs: Mapped[list["CrawlJob"]] = relationship(back_populates="subject")


class Regulation(Base):
    __tablename__ = "regulations"
    __table_args__ = (
        UniqueConstraint("uuid", name="uq_regulations_uuid"),
        UniqueConstraint("source_id", name="uq_regulations_source_id"),
        UniqueConstraint("detail_url", name="uq_regulations_detail_url"),
    )

    id: Mapped[int] = mapped_column(PRIMARY_KEY_TYPE, primary_key=True, autoincrement=True)
    uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        default=uuid.uuid4,
        index=True,
    )
    source_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    document_number: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    year: Mapped[int | None] = mapped_column(nullable=True)
    detail_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    subjects: Mapped[list[Subject]] = relationship(
        secondary="regulation_subjects",
        back_populates="regulations",
    )
    crawl_jobs: Mapped[list["CrawlJob"]] = relationship(back_populates="regulation")
    document_files: Mapped[list["DocumentFile"]] = relationship(back_populates="regulation")
    document_metadata: Mapped["DocumentMetadata | None"] = relationship(
        back_populates="regulation",
        uselist=False,
    )
    source_relations: Mapped[list["RegulationRelation"]] = relationship(
        foreign_keys="RegulationRelation.source_regulation_id",
        back_populates="source_regulation",
    )
    target_relations: Mapped[list["RegulationRelation"]] = relationship(
        foreign_keys="RegulationRelation.target_regulation_id",
        back_populates="target_regulation",
    )


class RegulationSubject(Base):
    __tablename__ = "regulation_subjects"

    id: Mapped[int] = mapped_column(PRIMARY_KEY_TYPE, primary_key=True, autoincrement=True)
    uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        default=uuid.uuid4,
        index=True,
    )
    regulation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("regulations.id", name="fk_regulation_subjects_regulation_id"),
        nullable=False,
        index=True,
    )
    subject_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("subjects.id", name="fk_regulation_subjects_subject_id"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("uuid", name="uq_regulation_subjects_uuid"),
        UniqueConstraint("regulation_id", "subject_id", name="uq_regulation_subjects_regulation_subject"),
    )


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"
    __table_args__ = (UniqueConstraint("uuid", name="uq_crawl_jobs_uuid"),)

    id: Mapped[int] = mapped_column(PRIMARY_KEY_TYPE, primary_key=True, autoincrement=True)
    uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        default=uuid.uuid4,
        index=True,
    )
    regulation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("regulations.id", name="fk_crawl_jobs_regulation_id"),
        nullable=True,
        index=True,
    )
    subject_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("subjects.id", name="fk_crawl_jobs_subject_id"),
        nullable=True,
        index=True,
    )
    stage: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    attempts: Mapped[int | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    regulation: Mapped[Regulation] = relationship(back_populates="crawl_jobs")
    subject: Mapped[Subject | None] = relationship(back_populates="crawl_jobs")


class DocumentFile(Base):
    __tablename__ = "document_files"
    __table_args__ = (
        UniqueConstraint("uuid", name="uq_document_files_uuid"),
        Index("uq_document_files_checksum_sha256", "checksum_sha256", unique=True),
    )

    id: Mapped[int] = mapped_column(PRIMARY_KEY_TYPE, primary_key=True, autoincrement=True)
    uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        default=uuid.uuid4,
        index=True,
    )
    regulation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("regulations.id", name="fk_document_files_regulation_id"),
        nullable=True,
        index=True,
    )
    hash: Mapped[str | None] = mapped_column(String, nullable=True)
    file_name: Mapped[str | None] = mapped_column(String, nullable=True)
    original_file_name: Mapped[str | None] = mapped_column(String, nullable=True)
    file_extension: Mapped[str | None] = mapped_column(String(32), nullable=True)
    disk: Mapped[str | None] = mapped_column(String, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    regulation: Mapped[Regulation] = relationship(back_populates="document_files")
    document_metadata: Mapped["DocumentMetadata | None"] = relationship(
        back_populates="document_file",
        uselist=False,
    )
    pages: Mapped[list["DocumentPage"]] = relationship(back_populates="document_file")


class DocumentMetadata(Base):
    __tablename__ = "document_metadata"
    __table_args__ = (
        UniqueConstraint("document_file_id", name="document_metadata_document_file_id_key"),
    )

    id: Mapped[int] = mapped_column(PRIMARY_KEY_TYPE, primary_key=True, autoincrement=True)
    document_file_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("document_files.id", name="fk_document_metadata_document_file_id"),
        nullable=True,
        unique=True,
        index=True,
    )
    regulation_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("regulations.id", name="fk_document_metadata_regulation_id"),
        nullable=True,
        unique=True,
        index=True,
    )
    document_type: Mapped[str | None] = mapped_column("document_type", String, nullable=True)
    title: Mapped[str | None] = mapped_column("title", String, nullable=True)
    teu: Mapped[str | None] = mapped_column("teu", String, nullable=True)
    number: Mapped[str | None] = mapped_column("number", String, nullable=True)
    form: Mapped[str | None] = mapped_column("form", String, nullable=True)
    form_short: Mapped[str | None] = mapped_column("form_short", String, nullable=True)
    year: Mapped[int | None] = mapped_column("year", nullable=True)
    place_of_enactment: Mapped[str | None] = mapped_column("place_of_enactment", String, nullable=True)
    enactment_date: Mapped[datetime | None] = mapped_column("enactment_date", Date, nullable=True)
    promulgation_date: Mapped[datetime | None] = mapped_column("promulgation_date", Date, nullable=True)
    effective_date: Mapped[datetime | None] = mapped_column("effective_date", Date, nullable=True)
    source: Mapped[str | None] = mapped_column("source", Text, nullable=True)
    subject: Mapped[str | None] = mapped_column("subject", String, nullable=True)
    status: Mapped[str | None] = mapped_column("status", String(50), nullable=True)
    language: Mapped[str | None] = mapped_column("language", String, nullable=True)
    location: Mapped[str | None] = mapped_column("location", String, nullable=True)
    field: Mapped[str | None] = mapped_column("field", String, nullable=True)
    alias: Mapped[str | None] = mapped_column("alias", String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    document_file: Mapped[DocumentFile | None] = relationship(back_populates="document_metadata")
    regulation: Mapped[Regulation | None] = relationship(back_populates="document_metadata")


class DocumentPage(Base):
    __tablename__ = "document_pages"
    __table_args__ = (
        UniqueConstraint("uuid", name="uq_document_pages_uuid"),
        UniqueConstraint("document_file_id", "page_number", name="uq_document_pages_document_file_page_number"),
    )

    id: Mapped[int] = mapped_column(PRIMARY_KEY_TYPE, primary_key=True, autoincrement=True)
    uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        default=uuid.uuid4,
        index=True,
    )
    document_file_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("document_files.id", name="fk_document_pages_document_file_id"),
        nullable=False,
        index=True,
    )
    page_number: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    document_file: Mapped[DocumentFile] = relationship(back_populates="pages")
    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document_page")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (UniqueConstraint("uuid", name="uq_document_chunks_uuid"),)

    id: Mapped[int] = mapped_column(PRIMARY_KEY_TYPE, primary_key=True, autoincrement=True)
    uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        default=uuid.uuid4,
        index=True,
    )
    document_page_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("document_pages.id", name="fk_document_chunks_document_page_id"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_metadata: Mapped[dict | None] = mapped_column(
        "metadata",
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    document_page: Mapped[DocumentPage] = relationship(back_populates="chunks")


class RegulationRelation(Base):
    __tablename__ = "regulation_relations"

    id: Mapped[int] = mapped_column(PRIMARY_KEY_TYPE, primary_key=True, autoincrement=True)
    uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        default=uuid.uuid4,
        index=True,
    )
    source_regulation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("regulations.id", name="fk_regulation_relations_source_regulation_id"),
        nullable=False,
        index=True,
    )
    target_regulation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("regulations.id", name="fk_regulation_relations_target_regulation_id"),
        nullable=False,
        index=True,
    )
    relation_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("uuid", name="uq_regulation_relations_uuid"),
        UniqueConstraint(
            "source_regulation_id",
            "target_regulation_id",
            "relation_type",
            name="uq_regulation_relations_source_target_type",
        ),
    )

    source_regulation: Mapped[Regulation] = relationship(
        foreign_keys=[source_regulation_id],
        back_populates="source_relations",
    )
    target_regulation: Mapped[Regulation] = relationship(
        foreign_keys=[target_regulation_id],
        back_populates="target_relations",
    )


__all__ = [
    "Base",
    "Subject",
    "Regulation",
    "RegulationSubject",
    "CrawlJob",
    "DocumentFile",
    "DocumentMetadata",
    "DocumentPage",
    "DocumentChunk",
    "RegulationRelation",
]
