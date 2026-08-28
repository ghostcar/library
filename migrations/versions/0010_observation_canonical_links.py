"""Link source observations to canonical works and series.

Revision ID: 0010
Revises: 0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("source_observations", sa.Column("work_id", sa.UUID(), nullable=True))
    op.add_column("source_observations", sa.Column("series_id", sa.UUID(), nullable=True))
    op.add_column(
        "source_observations",
        sa.Column("match_evidence", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_foreign_key(
        "fk_source_observations_work", "source_observations", "works", ["work_id"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_source_observations_series", "source_observations", "series", ["series_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_observations_owner_work", "source_observations", ["owner_id", "work_id"])
    op.create_index("ix_observations_owner_series", "source_observations", ["owner_id", "series_id"])


def downgrade() -> None:
    op.drop_index("ix_observations_owner_series", table_name="source_observations")
    op.drop_index("ix_observations_owner_work", table_name="source_observations")
    op.drop_constraint("fk_source_observations_series", "source_observations", type_="foreignkey")
    op.drop_constraint("fk_source_observations_work", "source_observations", type_="foreignkey")
    op.drop_column("source_observations", "match_evidence")
    op.drop_column("source_observations", "series_id")
    op.drop_column("source_observations", "work_id")
