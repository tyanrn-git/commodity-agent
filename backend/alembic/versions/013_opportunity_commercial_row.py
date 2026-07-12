"""opportunity indicative economics and monitoring access

Revision ID: 013
Revises: 012
Create Date: 2026-07-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "opportunities",
        sa.Column(
            "indicative_economics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "monitoring_rules",
        sa.Column("access_mode", sa.String(length=32), nullable=False, server_default="PUBLIC"),
    )
    op.add_column(
        "monitoring_rules",
        sa.Column(
            "connector_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("monitoring_rules", "connector_config")
    op.drop_column("monitoring_rules", "access_mode")
    op.drop_column("opportunities", "indicative_economics")
