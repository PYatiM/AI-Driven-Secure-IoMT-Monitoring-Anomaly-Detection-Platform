"""add anomaly fields to device_data

Revision ID: 20260331_000001
Revises: 20260325_000001
Create Date: 2026-03-31 00:00:01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260331_000001"
down_revision: Union[str, None] = "20260325_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "device_data",
        sa.Column(
            "anomaly_flag",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column("device_data", sa.Column("anomaly_score", sa.Float(), nullable=True))
    op.add_column("device_data", sa.Column("confidence_score", sa.Float(), nullable=True))
    op.add_column("device_data", sa.Column("model_name", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("device_data", "model_name")
    op.drop_column("device_data", "confidence_score")
    op.drop_column("device_data", "anomaly_score")
    op.drop_column("device_data", "anomaly_flag")
