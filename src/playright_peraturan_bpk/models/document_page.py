from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import UUID, BigInteger, DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import PRIMARY_KEY_TYPE, Base

if TYPE_CHECKING:
    from .document_chunk import DocumentChunk
    from .document_file import DocumentFile


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
    chunks: Mapped[list[DocumentChunk]] = relationship(back_populates="document_page")
