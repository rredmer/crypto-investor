"""risk metric history

Revision ID: 002
Revises: 001
Create Date: 2026-02-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "risk_metric_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portfolio_id", sa.Integer(), nullable=False, index=True),
        sa.Column("var_95", sa.Float(), server_default="0.0"),
        sa.Column("var_99", sa.Float(), server_default="0.0"),
        sa.Column("cvar_95", sa.Float(), server_default="0.0"),
        sa.Column("cvar_99", sa.Float(), server_default="0.0"),
        sa.Column("method", sa.String(20), server_default="parametric"),
        sa.Column("drawdown", sa.Float(), server_default="0.0"),
        sa.Column("equity", sa.Float(), server_default="0.0"),
        sa.Column("open_positions_count", sa.Integer(), server_default="0"),
        sa.Column("recorded_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("risk_metric_history")
