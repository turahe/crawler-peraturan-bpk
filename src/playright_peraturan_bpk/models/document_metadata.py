from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import PRIMARY_KEY_TYPE, Base

if TYPE_CHECKING:
    from .document_file import DocumentFile
    from .regulation import Regulation


class DocumentMetadata(Base):
    __tablename__ = "document_metadata"
    __table_args__ = (UniqueConstraint("document_file_id", name="document_metadata_document_file_id_key"),)

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
