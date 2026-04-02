"""encrypt sensitive data at rest

Revision ID: 20260402_000001
Revises: 20260331_000001
Create Date: 2026-04-02 00:00:01
"""

from __future__ import annotations

import base64
import json
import os
from hashlib import sha256
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from cryptography.fernet import Fernet
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision: str = "20260402_000001"
down_revision: Union[str, None] = "20260331_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_DATA_ENCRYPTION_KEY = "change-this-data-encryption-key-in-production"
ENCRYPTION_PREFIX = "enc::"


def _build_fernet() -> Fernet:
    secret = os.getenv("DATA_ENCRYPTION_KEY", DEFAULT_DATA_ENCRYPTION_KEY)
    key = base64.urlsafe_b64encode(sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def _encrypt_value(fernet: Fernet, value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and value.startswith(ENCRYPTION_PREFIX):
        return value

    if not isinstance(value, str):
        value = json.dumps(value, separators=(",", ":"), sort_keys=True, default=str)

    token = fernet.encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{ENCRYPTION_PREFIX}{token}"


def _decrypt_value(fernet: Fernet, value):
    if value is None:
        return None
    if not isinstance(value, str) or not value.startswith(ENCRYPTION_PREFIX):
        return value

    token = value[len(ENCRYPTION_PREFIX) :]
    return fernet.decrypt(token.encode("utf-8")).decode("utf-8")


def _rewrite_columns(
    bind: Connection,
    table_name: str,
    id_column: str,
    columns: tuple[str, ...],
    transform,
) -> None:
    select_columns = ", ".join((id_column, *columns))
    rows = bind.execute(
        sa.text(f"SELECT {select_columns} FROM {table_name}")
    ).mappings()

    for row in rows:
        updates = {}
        for column in columns:
            current_value = row[column]
            transformed_value = transform(current_value)
            if transformed_value != current_value:
                updates[column] = transformed_value

        if not updates:
            continue

        assignments = ", ".join(f"{column} = :{column}" for column in updates)
        bind.execute(
            sa.text(
                f"UPDATE {table_name} SET {assignments} WHERE {id_column} = :row_id"
            ),
            {**updates, "row_id": row[id_column]},
        )


def upgrade() -> None:
    bind = op.get_bind()
    fernet = _build_fernet()

    op.alter_column(
        "users",
        "full_name",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=False,
    )
    op.alter_column(
        "devices",
        "location",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "devices",
        "ip_address",
        existing_type=sa.String(length=45),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "device_data",
        "payload",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=sa.Text(),
        existing_nullable=True,
        postgresql_using="payload::text",
    )

    _rewrite_columns(
        bind,
        "users",
        "id",
        ("full_name",),
        lambda value: _encrypt_value(fernet, value),
    )
    _rewrite_columns(
        bind,
        "devices",
        "id",
        ("location", "ip_address"),
        lambda value: _encrypt_value(fernet, value),
    )
    _rewrite_columns(
        bind,
        "device_data",
        "id",
        ("value_text", "payload"),
        lambda value: _encrypt_value(fernet, value),
    )
    _rewrite_columns(
        bind,
        "alerts",
        "id",
        ("description",),
        lambda value: _encrypt_value(fernet, value),
    )


def downgrade() -> None:
    bind = op.get_bind()
    fernet = _build_fernet()

    _rewrite_columns(
        bind,
        "users",
        "id",
        ("full_name",),
        lambda value: _decrypt_value(fernet, value),
    )
    _rewrite_columns(
        bind,
        "devices",
        "id",
        ("location", "ip_address"),
        lambda value: _decrypt_value(fernet, value),
    )
    _rewrite_columns(
        bind,
        "device_data",
        "id",
        ("value_text", "payload"),
        lambda value: _decrypt_value(fernet, value),
    )
    _rewrite_columns(
        bind,
        "alerts",
        "id",
        ("description",),
        lambda value: _decrypt_value(fernet, value),
    )

    op.alter_column(
        "device_data",
        "payload",
        existing_type=sa.Text(),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=True,
        postgresql_using="payload::jsonb",
    )
    op.alter_column(
        "devices",
        "ip_address",
        existing_type=sa.Text(),
        type_=sa.String(length=45),
        existing_nullable=True,
    )
    op.alter_column(
        "devices",
        "location",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "users",
        "full_name",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
