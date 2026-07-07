"""Merge Kiri and cloud asset migration heads.

Revision ID: 20260708_0010
Revises: 20260628_0008, 20260708_0009
Create Date: 2026-07-08
"""

from __future__ import annotations

from collections.abc import Sequence


revision: str = "20260708_0010"
down_revision: tuple[str, str] = ("20260628_0008", "20260708_0009")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
