"""internet source fetch strategies

Revision ID: 017
Revises: 016
Create Date: 2026-07-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "internet_sources",
        sa.Column("fetch_strategy", sa.String(length=32), nullable=False, server_default="HTML"),
    )
    op.add_column(
        "internet_sources",
        sa.Column("fetch_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("internet_sources", "fetch_config")
    op.drop_column("internet_sources", "fetch_strategy")
