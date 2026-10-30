from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import UUID, BigInteger, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import PRIMARY_KEY_TYPE, Base


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
