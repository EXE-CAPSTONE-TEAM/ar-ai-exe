"""Add normal map columns to model_assets.

Revision ID: 20260530_0006
Revises: 20260527_0005
Create Date: 2026-05-30
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260530_0006"
down_revision: str | None = "20260527_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("model_assets", sa.Column("normal_map_path", sa.Text(), nullable=True))
    op.add_column("model_assets", sa.Column("normal_map_size_bytes", sa.Integer(), nullable=True))
    op.add_column(
        "model_assets", sa.Column("normal_map_content_type", sa.String(length=120), nullable=True)
    )
    op.add_column(
        "model_assets", sa.Column("normal_map_checksum", sa.String(length=128), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("model_assets", "normal_map_checksum")
    op.drop_column("model_assets", "normal_map_content_type")
    op.drop_column("model_assets", "normal_map_size_bytes")
    op.drop_column("model_assets", "normal_map_path")
