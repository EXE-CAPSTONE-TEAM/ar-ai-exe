"""Add uploaded design assets.

Revision ID: 20260528_0006
Revises: 20260527_0005
Create Date: 2026-05-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260528_0006"
down_revision: str | None = "20260527_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "design_assets",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("file_name", sa.String(length=180), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_design_assets_source_type", "design_assets", ["source_type"])
    op.create_index("ix_design_assets_user_id", "design_assets", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_design_assets_user_id", table_name="design_assets")
    op.drop_index("ix_design_assets_source_type", table_name="design_assets")
    op.drop_table("design_assets")
