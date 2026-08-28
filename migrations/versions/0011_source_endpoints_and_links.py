"""Add abstract source endpoints and canonical entity links.

Revision ID: 0011
Revises: 0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_endpoints",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("owner_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(16), nullable=False),
        sa.Column("role", sa.String(24), nullable=False, server_default=sa.text("'metadata'")),
        sa.Column("adapter_id", sa.String(32), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_source_endpoints_owner", "source_endpoints", ["owner_id"])
    op.create_table(
        "source_links",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("owner_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_endpoint_id", sa.UUID(), sa.ForeignKey("source_endpoints.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", sa.String(16), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(24), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("external_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("source_endpoint_id", "entity_type", "entity_id", "role", name="uq_source_links_entity_role"),
    )
    op.create_index("ix_source_links_owner_entity", "source_links", ["owner_id", "entity_type", "entity_id"])
    op.add_column("watch_rules", sa.Column("source_endpoint_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_watch_rules_source_endpoint", "watch_rules", "source_endpoints", ["source_endpoint_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint("fk_watch_rules_source_endpoint", "watch_rules", type_="foreignkey")
    op.drop_column("watch_rules", "source_endpoint_id")
    op.drop_index("ix_source_links_owner_entity", table_name="source_links")
    op.drop_table("source_links")
    op.drop_index("ix_source_endpoints_owner", table_name="source_endpoints")
    op.drop_table("source_endpoints")
