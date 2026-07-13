"""search run product_id

Revision ID: 020
Revises: 019
Create Date: 2026-07-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "internet_source_search_runs",
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_internet_source_search_runs_product_id",
        "internet_source_search_runs",
        "products",
        ["product_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_internet_source_search_runs_product_id"),
        "internet_source_search_runs",
        ["product_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_internet_source_search_runs_product_id"), table_name="internet_source_search_runs")
    op.drop_constraint("fk_internet_source_search_runs_product_id", "internet_source_search_runs", type_="foreignkey")
    op.drop_column("internet_source_search_runs", "product_id")
