"""add security events

Revision ID: 20260404_000002
Revises: 20260404_000001
Create Date: 2026-04-04 00:00:02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260404_000002"
down_revision: Union[str, None] = "20260404_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "security_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column(
            "severity",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'medium'"),
        ),
        sa.Column(
            "outcome",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'detected'"),
        ),
        sa.Column(
            "actor_type",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'anonymous'"),
        ),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_device_id", sa.Integer(), nullable=True),
        sa.Column("http_method", sa.String(length=10), nullable=True),
        sa.Column("path", sa.String(length=255), nullable=True),
        sa.Column("resource_type", sa.String(length=100), nullable=True),
        sa.Column("resource_id", sa.String(length=100), nullable=True),
        sa.Column("ip_address", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_device_id"], ["devices.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_security_events_occurred_at",
        "security_events",
        ["occurred_at"],
    )
    op.create_index(
        "ix_security_events_category_severity",
        "security_events",
        ["category", "severity"],
    )
    op.create_index(
        "ix_security_events_event_type_occurred_at",
        "security_events",
        ["event_type", "occurred_at"],
    )
    op.create_index(
        "ix_security_events_actor_user",
        "security_events",
        ["actor_user_id", "occurred_at"],
    )
    op.create_index(
        "ix_security_events_actor_device",
        "security_events",
        ["actor_device_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_security_events_actor_device", table_name="security_events")
    op.drop_index("ix_security_events_actor_user", table_name="security_events")
    op.drop_index(
        "ix_security_events_event_type_occurred_at",
        table_name="security_events",
    )
    op.drop_index(
        "ix_security_events_category_severity",
        table_name="security_events",
    )
    op.drop_index("ix_security_events_occurred_at", table_name="security_events")
    op.drop_table("security_events")
