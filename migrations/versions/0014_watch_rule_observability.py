"""Add parser and last-poll observability to watch rules.

Revision ID: 0014
Revises: 0013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("watch_rules", sa.Column("parser_version", sa.String(length=64)))
    op.add_column("watch_rules", sa.Column("last_status", sa.String(length=24)))
    op.add_column("watch_rules", sa.Column("last_new_count", sa.Integer()))
    op.add_column("watch_rules", sa.Column("last_not_modified", sa.Boolean()))
    op.add_column("watch_rules", sa.Column("last_duration_ms", sa.Integer()))


def downgrade() -> None:
    op.drop_column("watch_rules", "last_duration_ms")
    op.drop_column("watch_rules", "last_not_modified")
    op.drop_column("watch_rules", "last_new_count")
    op.drop_column("watch_rules", "last_status")
    op.drop_column("watch_rules", "parser_version")
