"""Add durable outbox retry scheduling.

Revision ID: 0009
Revises: 0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "outbox_events",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_outbox_events_pending_retry",
        "outbox_events",
        ["status", "next_attempt_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_events_pending_retry", table_name="outbox_events")
    op.drop_column("outbox_events", "next_attempt_at")
