from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import UUID, BigInteger, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import PRIMARY_KEY_TYPE, Base

if TYPE_CHECKING:
    from .regulation import Regulation
    from .subject import Subject


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
