"""Add Kiri scan task state.

Revision ID: 20260628_0008
Revises: 20260612_0007
Create Date: 2026-06-28
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260628_0008"
down_revision: str | None = "20260612_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "kiri_scan_tasks",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("scan_session_id", sa.String(length=64), nullable=False),
        sa.Column("provider_serialize", sa.String(length=160), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("provider_status", sa.String(length=32), nullable=True),
        sa.Column("source_glb_path", sa.Text(), nullable=True),
        sa.Column("crop_box_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["scan_session_id"], ["scan_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_serialize"),
        sa.UniqueConstraint("scan_session_id"),
    )
    op.create_index("ix_kiri_scan_tasks_scan_session_id", "kiri_scan_tasks", ["scan_session_id"])
    op.create_index("ix_kiri_scan_tasks_status", "kiri_scan_tasks", ["status"])


def downgrade() -> None:
    op.drop_index("ix_kiri_scan_tasks_status", table_name="kiri_scan_tasks")
    op.drop_index("ix_kiri_scan_tasks_scan_session_id", table_name="kiri_scan_tasks")
    op.drop_table("kiri_scan_tasks")
