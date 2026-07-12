"""opportunity source_url and internet source is_test

Revision ID: 018
Revises: 017
Create Date: 2026-07-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("opportunities", sa.Column("source_url", sa.String(length=2048), nullable=True))
    op.add_column(
        "internet_sources",
        sa.Column("is_test", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("internet_sources", "is_test")
    op.drop_column("opportunities", "source_url")
