"""Owner-scope external source identifiers.

Revision ID: 0008
Revises: 0007
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_source_records_adapter_external", "source_records", type_="unique")
    op.create_unique_constraint(
        "uq_source_records_owner_adapter_external",
        "source_records",
        ["owner_id", "adapter_id", "external_id"],
    )
    op.drop_constraint("uq_source_author_records_uniq", "source_author_records", type_="unique")
    op.create_unique_constraint(
        "uq_source_author_records_owner_adapter_external",
        "source_author_records",
        ["owner_id", "adapter_id", "external_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_source_author_records_owner_adapter_external",
        "source_author_records",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_source_author_records_uniq",
        "source_author_records",
        ["adapter_id", "external_id"],
    )
    op.drop_constraint(
        "uq_source_records_owner_adapter_external",
        "source_records",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_source_records_adapter_external",
        "source_records",
        ["adapter_id", "external_id"],
    )
