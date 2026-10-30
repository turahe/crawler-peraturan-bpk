from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import UUID, DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import PRIMARY_KEY_TYPE, Base

if TYPE_CHECKING:
    from .crawl_job import CrawlJob
    from .regulation import Regulation


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

    regulations: Mapped[list[Regulation]] = relationship(
        secondary="regulation_subjects",
        back_populates="subjects",
    )
    crawl_jobs: Mapped[list[CrawlJob]] = relationship(back_populates="subject")
