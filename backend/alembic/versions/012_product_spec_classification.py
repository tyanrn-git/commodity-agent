"""product spec classification and assistant

Revision ID: 012
Revises: 011
Create Date: 2026-07-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "product_specification_profiles",
        sa.Column("parameter_kind", sa.String(length=32), nullable=False, server_default="VARIANT"),
    )
    op.add_column(
        "product_specification_profiles",
        sa.Column("variation_materiality", sa.String(length=32), nullable=False, server_default="UNKNOWN"),
    )
    op.add_column(
        "product_specification_profiles",
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.add_column(
        "product_specification_profiles",
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("product_specification_profiles", "evidence_count")
    op.drop_column("product_specification_profiles", "description")
    op.drop_column("product_specification_profiles", "variation_materiality")
    op.drop_column("product_specification_profiles", "parameter_kind")
