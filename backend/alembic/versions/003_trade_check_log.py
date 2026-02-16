"""trade check log

Revision ID: 003
Revises: 002
Create Date: 2026-02-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "trade_check_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portfolio_id", sa.Integer(), nullable=False, index=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("size", sa.Float(), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("stop_loss_price", sa.Float(), nullable=True),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("equity_at_check", sa.Float(), server_default="0.0"),
        sa.Column("drawdown_at_check", sa.Float(), server_default="0.0"),
        sa.Column("open_positions_at_check", sa.Integer(), server_default="0"),
        sa.Column("checked_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("trade_check_log")
