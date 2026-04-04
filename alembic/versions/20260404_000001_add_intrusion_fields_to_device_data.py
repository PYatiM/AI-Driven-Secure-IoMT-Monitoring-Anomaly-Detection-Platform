"""add intrusion fields to device_data

Revision ID: 20260404_000001
Revises: 20260403_000001
Create Date: 2026-04-04 00:00:01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260404_000001"
down_revision: Union[str, None] = "20260403_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "device_data",
        sa.Column(
            "intrusion_flag",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column("device_data", sa.Column("intrusion_score", sa.Float(), nullable=True))
    op.add_column(
        "device_data",
        sa.Column("intrusion_type", sa.String(length=100), nullable=True),
    )
    op.add_column("device_data", sa.Column("intrusion_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("device_data", "intrusion_reason")
    op.drop_column("device_data", "intrusion_type")
    op.drop_column("device_data", "intrusion_score")
    op.drop_column("device_data", "intrusion_flag")
