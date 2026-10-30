from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import UUID, DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import PRIMARY_KEY_TYPE, Base

if TYPE_CHECKING:
    from .crawl_job import CrawlJob
    from .document_file import DocumentFile
    from .document_metadata import DocumentMetadata
    from .regulation_relation import RegulationRelation
    from .subject import Subject


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
    crawl_jobs: Mapped[list[CrawlJob]] = relationship(back_populates="regulation")
    document_files: Mapped[list[DocumentFile]] = relationship(back_populates="regulation")
    document_metadata: Mapped[DocumentMetadata | None] = relationship(
        back_populates="regulation",
        uselist=False,
    )
    source_relations: Mapped[list[RegulationRelation]] = relationship(
        foreign_keys="RegulationRelation.source_regulation_id",
        back_populates="source_regulation",
    )
    target_relations: Mapped[list[RegulationRelation]] = relationship(
        foreign_keys="RegulationRelation.target_regulation_id",
        back_populates="target_regulation",
    )
