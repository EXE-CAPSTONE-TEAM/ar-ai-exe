"""Add canonical control-plane identity to mobile scan sessions.

Revision ID: 20260715_0009
Revises: 20260708_0010
Create Date: 2026-07-15
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260715_0009"
down_revision: str | None = "20260708_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


OWNER_PLANE_CHECK = """
(
    user_id IS NOT NULL
    AND control_plane_user_id IS NULL
    AND control_plane_project_id IS NULL
    AND control_plane_completion_token IS NULL
)
OR
(
    user_id IS NULL
    AND control_plane_user_id IS NOT NULL
    AND control_plane_project_id IS NOT NULL
    AND control_plane_completion_token IS NOT NULL
)
"""


def upgrade() -> None:
    with op.batch_alter_table("scan_sessions") as batch_op:
        batch_op.alter_column(
            "user_id",
            existing_type=sa.String(length=64),
            nullable=True,
        )
        batch_op.add_column(sa.Column("control_plane_user_id", sa.String(length=36), nullable=True))
        batch_op.add_column(
            sa.Column("control_plane_project_id", sa.String(length=36), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "control_plane_completion_token",
                sa.String(length=256),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "control_plane_model_asset_id",
                sa.String(length=36),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column("control_plane_project_name", sa.String(length=100), nullable=True)
        )
        batch_op.add_column(sa.Column("control_plane_published_at", sa.DateTime(), nullable=True))
        batch_op.create_index(
            "ix_scan_sessions_control_plane_user_id",
            ["control_plane_user_id"],
            unique=False,
        )
        batch_op.create_unique_constraint(
            "uq_scan_sessions_control_plane_project_id",
            ["control_plane_project_id"],
        )
        batch_op.create_check_constraint(
            "ck_scan_sessions_owner_plane",
            OWNER_PLANE_CHECK,
        )


def downgrade() -> None:
    with op.batch_alter_table("scan_sessions") as batch_op:
        batch_op.drop_constraint(
            "ck_scan_sessions_owner_plane",
            type_="check",
        )
        batch_op.drop_constraint(
            "uq_scan_sessions_control_plane_project_id",
            type_="unique",
        )
        batch_op.drop_index("ix_scan_sessions_control_plane_user_id")
        batch_op.drop_column("control_plane_published_at")
        batch_op.drop_column("control_plane_project_name")
        batch_op.drop_column("control_plane_model_asset_id")
        batch_op.drop_column("control_plane_completion_token")
        batch_op.drop_column("control_plane_project_id")
        batch_op.drop_column("control_plane_user_id")
        batch_op.alter_column(
            "user_id",
            existing_type=sa.String(length=64),
            nullable=False,
        )
