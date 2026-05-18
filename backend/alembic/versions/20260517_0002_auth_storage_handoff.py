"""Add JWT user fields, handoff URLs, and artifact metadata.

Revision ID: 20260517_0002
Revises: 20260517_0001
Create Date: 2026-05-17
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260517_0002"
down_revision: str | None = "20260517_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("updated_at", sa.DateTime(), nullable=True))

    op.add_column("scan_sessions", sa.Column("web_design_url", sa.Text(), nullable=True))
    op.add_column("scan_sessions", sa.Column("raw_video_size_bytes", sa.Integer(), nullable=True))
    op.add_column("scan_sessions", sa.Column("raw_video_content_type", sa.String(length=120), nullable=True))
    op.add_column("scan_sessions", sa.Column("raw_video_checksum", sa.String(length=128), nullable=True))
    op.add_column("scan_sessions", sa.Column("metadata_size_bytes", sa.Integer(), nullable=True))
    op.add_column("scan_sessions", sa.Column("metadata_content_type", sa.String(length=120), nullable=True))
    op.add_column("scan_sessions", sa.Column("metadata_checksum", sa.String(length=128), nullable=True))

    for prefix in ["glb", "obj", "mtl", "texture", "quality_report"]:
        op.add_column("model_assets", sa.Column(f"{prefix}_size_bytes", sa.Integer(), nullable=True))
        op.add_column("model_assets", sa.Column(f"{prefix}_content_type", sa.String(length=120), nullable=True))
        op.add_column("model_assets", sa.Column(f"{prefix}_checksum", sa.String(length=128), nullable=True))

    op.add_column("export_packages", sa.Column("zip_size_bytes", sa.Integer(), nullable=True))
    op.add_column("export_packages", sa.Column("zip_content_type", sa.String(length=120), nullable=True))
    op.add_column("export_packages", sa.Column("zip_checksum", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("export_packages", "zip_checksum")
    op.drop_column("export_packages", "zip_content_type")
    op.drop_column("export_packages", "zip_size_bytes")

    for prefix in reversed(["glb", "obj", "mtl", "texture", "quality_report"]):
        op.drop_column("model_assets", f"{prefix}_checksum")
        op.drop_column("model_assets", f"{prefix}_content_type")
        op.drop_column("model_assets", f"{prefix}_size_bytes")

    op.drop_column("scan_sessions", "metadata_checksum")
    op.drop_column("scan_sessions", "metadata_content_type")
    op.drop_column("scan_sessions", "metadata_size_bytes")
    op.drop_column("scan_sessions", "raw_video_checksum")
    op.drop_column("scan_sessions", "raw_video_content_type")
    op.drop_column("scan_sessions", "raw_video_size_bytes")
    op.drop_column("scan_sessions", "web_design_url")

    op.drop_column("users", "updated_at")
    op.drop_column("users", "password_hash")