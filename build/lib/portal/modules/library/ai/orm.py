"""ORM models: AI proposal cache and user corrections (evaluation dataset)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from portal.core.database.engine import Base


class AIProposalModel(Base):
    """Proposal cache: digest_hash + model + prompt/schema versions (§8.6)."""

    __tablename__ = "ai_proposals"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    digest_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[int] = mapped_column(nullable=False, default=1)
    schema_version: Mapped[int] = mapped_column(nullable=False, default=1)
    proposal: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index(
            "uq_ai_proposals_cache",
            "digest_hash",
            "model",
            "prompt_version",
            "schema_version",
            unique=True,
        ),
    )


class AICorrectionModel(Base):
    """Confirmed user corrections — local evaluation dataset (§8.6, no auto-finetune)."""

    __tablename__ = "ai_corrections"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    import_item_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("import_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    digest_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    proposal: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    applied: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="llm")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (Index("ix_ai_corrections_owner_created", "owner_id", "created_at"),)
