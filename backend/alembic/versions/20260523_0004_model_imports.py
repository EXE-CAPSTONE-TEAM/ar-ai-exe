"""Add source metadata for imported model sessions.

Revision ID: 20260523_0004
Revises: 20260519_0003
Create Date: 2026-05-23
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260523_0004"
down_revision: str | None = "20260519_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "scan_sessions",
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="scan"),
    )
    op.add_column("scan_sessions", sa.Column("import_name", sa.String(length=160), nullable=True))
    op.create_index("ix_scan_sessions_source_type", "scan_sessions", ["source_type"])


def downgrade() -> None:
    op.drop_index("ix_scan_sessions_source_type", table_name="scan_sessions")
    op.drop_column("scan_sessions", "import_name")
    op.drop_column("scan_sessions", "source_type")
