"""add alert escalation fields

Revision ID: 20260404_000003
Revises: 20260404_000002
Create Date: 2026-04-04 00:00:03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260404_000003"
down_revision: Union[str, None] = "20260404_000002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "alerts",
        sa.Column(
            "escalated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "alerts",
        sa.Column("escalation_level", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("escalation_target", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("escalation_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_alerts_escalated_triggered_at",
        "alerts",
        ["escalated", "triggered_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_alerts_escalated_triggered_at", table_name="alerts")
    op.drop_column("alerts", "escalated_at")
    op.drop_column("alerts", "escalation_reason")
    op.drop_column("alerts", "escalation_target")
    op.drop_column("alerts", "escalation_level")
    op.drop_column("alerts", "escalated")
