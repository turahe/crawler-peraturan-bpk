from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import UUID, BigInteger, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import PRIMARY_KEY_TYPE, Base

if TYPE_CHECKING:
    from .regulation import Regulation


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
