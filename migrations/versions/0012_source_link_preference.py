"""Add preferred source-link ordering.

Revision ID: 0012
Revises: 0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "source_links",
        sa.Column("is_preferred", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "source_links",
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("100")),
    )
    op.create_index(
        "uq_source_links_preferred_role",
        "source_links",
        ["owner_id", "entity_type", "entity_id", "role"],
        unique=True,
        postgresql_where=sa.text("is_preferred"),
    )


def downgrade() -> None:
    op.drop_index("uq_source_links_preferred_role", table_name="source_links")
    op.drop_column("source_links", "priority")
    op.drop_column("source_links", "is_preferred")
