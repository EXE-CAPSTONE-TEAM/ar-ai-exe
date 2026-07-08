"""Add asset delete policies and optional design base asset version.

Revision ID: 20260708_0009
Revises: 20260702_0008
Create Date: 2026-07-08
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260708_0009"
down_revision: str | None = "20260702_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
}


def upgrade() -> None:
    if _is_sqlite():
        _upgrade_sqlite()
        return

    op.add_column(
        "designs",
        sa.Column("base_asset_version_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_designs_base_asset_version_id",
        "designs",
        ["base_asset_version_id"],
    )
    op.alter_column(
        "designs",
        "model_asset_id",
        existing_type=sa.String(length=64),
        nullable=True,
    )

    _drop_foreign_keys("designs", ["model_asset_id"], "model_assets")
    op.create_foreign_key(
        "fk_designs_model_asset_id_model_assets",
        "designs",
        "model_assets",
        ["model_asset_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_designs_base_asset_version_id_asset_versions",
        "designs",
        "asset_versions",
        ["base_asset_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    _drop_foreign_keys("asset_versions", ["project_id"], "projects")
    _drop_foreign_keys("asset_versions", ["parent_asset_version_id"], "asset_versions")
    op.create_foreign_key(
        "fk_asset_versions_project_id_projects",
        "asset_versions",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_asset_versions_parent_asset_version_id_asset_versions",
        "asset_versions",
        "asset_versions",
        ["parent_asset_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    _drop_foreign_keys("asset_version_files", ["asset_version_id"], "asset_versions")
    op.create_foreign_key(
        "fk_asset_version_files_asset_version_id_asset_versions",
        "asset_version_files",
        "asset_versions",
        ["asset_version_id"],
        ["id"],
        ondelete="CASCADE",
    )

    _drop_foreign_keys("asset_version_legacy_links", ["asset_version_id"], "asset_versions")
    op.drop_constraint(
        "uq_asset_version_legacy_links_identity",
        "asset_version_legacy_links",
        type_="unique",
    )
    op.create_foreign_key(
        "fk_asset_version_legacy_links_asset_version_id_asset_versions",
        "asset_version_legacy_links",
        "asset_versions",
        ["asset_version_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_asset_version_legacy_links_legacy_identity",
        "asset_version_legacy_links",
        ["legacy_type", "legacy_id"],
    )
    op.create_unique_constraint(
        "uq_asset_version_legacy_links_version_type",
        "asset_version_legacy_links",
        ["asset_version_id", "legacy_type"],
    )


def downgrade() -> None:
    if _is_sqlite():
        _downgrade_sqlite()
        return

    op.drop_constraint(
        "uq_asset_version_legacy_links_version_type",
        "asset_version_legacy_links",
        type_="unique",
    )
    op.drop_constraint(
        "uq_asset_version_legacy_links_legacy_identity",
        "asset_version_legacy_links",
        type_="unique",
    )
    _drop_foreign_keys("asset_version_legacy_links", ["asset_version_id"], "asset_versions")
    op.create_foreign_key(
        "fk_asset_version_legacy_links_asset_version_id_asset_versions",
        "asset_version_legacy_links",
        "asset_versions",
        ["asset_version_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_asset_version_legacy_links_identity",
        "asset_version_legacy_links",
        ["legacy_type", "legacy_id", "asset_version_id"],
    )

    _drop_foreign_keys("asset_version_files", ["asset_version_id"], "asset_versions")
    op.create_foreign_key(
        "fk_asset_version_files_asset_version_id_asset_versions",
        "asset_version_files",
        "asset_versions",
        ["asset_version_id"],
        ["id"],
    )

    _drop_foreign_keys("asset_versions", ["parent_asset_version_id"], "asset_versions")
    _drop_foreign_keys("asset_versions", ["project_id"], "projects")
    op.create_foreign_key(
        "fk_asset_versions_parent_asset_version_id_asset_versions",
        "asset_versions",
        "asset_versions",
        ["parent_asset_version_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_asset_versions_project_id_projects",
        "asset_versions",
        "projects",
        ["project_id"],
        ["id"],
    )

    _drop_foreign_keys("designs", ["base_asset_version_id"], "asset_versions")
    _drop_foreign_keys("designs", ["model_asset_id"], "model_assets")
    op.drop_index("ix_designs_base_asset_version_id", table_name="designs")
    op.drop_column("designs", "base_asset_version_id")
    op.alter_column(
        "designs",
        "model_asset_id",
        existing_type=sa.String(length=64),
        nullable=False,
    )
    op.create_foreign_key(
        "fk_designs_model_asset_id_model_assets",
        "designs",
        "model_assets",
        ["model_asset_id"],
        ["id"],
    )


def _upgrade_sqlite() -> None:
    with op.batch_alter_table("designs", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.add_column(sa.Column("base_asset_version_id", sa.String(length=64), nullable=True))
        batch_op.alter_column(
            "model_asset_id",
            existing_type=sa.String(length=64),
            nullable=True,
        )
        batch_op.drop_constraint("fk_designs_model_asset_id_model_assets", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_designs_model_asset_id_model_assets",
            "model_assets",
            ["model_asset_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_designs_base_asset_version_id_asset_versions",
            "asset_versions",
            ["base_asset_version_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_designs_base_asset_version_id", ["base_asset_version_id"])

    with op.batch_alter_table("asset_versions", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.drop_constraint("fk_asset_versions_project_id_projects", type_="foreignkey")
        batch_op.drop_constraint(
            "fk_asset_versions_parent_asset_version_id_asset_versions",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "fk_asset_versions_project_id_projects",
            "projects",
            ["project_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            "fk_asset_versions_parent_asset_version_id_asset_versions",
            "asset_versions",
            ["parent_asset_version_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("asset_version_files", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.drop_constraint(
            "fk_asset_version_files_asset_version_id_asset_versions",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "fk_asset_version_files_asset_version_id_asset_versions",
            "asset_versions",
            ["asset_version_id"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table(
        "asset_version_legacy_links",
        naming_convention=NAMING_CONVENTION,
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_asset_version_legacy_links_asset_version_id_asset_versions",
            type_="foreignkey",
        )
        batch_op.drop_constraint("uq_asset_version_legacy_links_identity", type_="unique")
        batch_op.create_foreign_key(
            "fk_asset_version_legacy_links_asset_version_id_asset_versions",
            "asset_versions",
            ["asset_version_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_unique_constraint(
            "uq_asset_version_legacy_links_legacy_identity",
            ["legacy_type", "legacy_id"],
        )
        batch_op.create_unique_constraint(
            "uq_asset_version_legacy_links_version_type",
            ["asset_version_id", "legacy_type"],
        )


def _downgrade_sqlite() -> None:
    with op.batch_alter_table(
        "asset_version_legacy_links",
        naming_convention=NAMING_CONVENTION,
    ) as batch_op:
        batch_op.drop_constraint("uq_asset_version_legacy_links_version_type", type_="unique")
        batch_op.drop_constraint("uq_asset_version_legacy_links_legacy_identity", type_="unique")
        batch_op.drop_constraint(
            "fk_asset_version_legacy_links_asset_version_id_asset_versions",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "fk_asset_version_legacy_links_asset_version_id_asset_versions",
            "asset_versions",
            ["asset_version_id"],
            ["id"],
        )
        batch_op.create_unique_constraint(
            "uq_asset_version_legacy_links_identity",
            ["legacy_type", "legacy_id", "asset_version_id"],
        )

    with op.batch_alter_table("asset_version_files", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.drop_constraint(
            "fk_asset_version_files_asset_version_id_asset_versions",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "fk_asset_version_files_asset_version_id_asset_versions",
            "asset_versions",
            ["asset_version_id"],
            ["id"],
        )

    with op.batch_alter_table("asset_versions", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.drop_constraint(
            "fk_asset_versions_parent_asset_version_id_asset_versions",
            type_="foreignkey",
        )
        batch_op.drop_constraint("fk_asset_versions_project_id_projects", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_asset_versions_parent_asset_version_id_asset_versions",
            "asset_versions",
            ["parent_asset_version_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_asset_versions_project_id_projects",
            "projects",
            ["project_id"],
            ["id"],
        )

    with op.batch_alter_table("designs", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.drop_index("ix_designs_base_asset_version_id")
        batch_op.drop_constraint(
            "fk_designs_base_asset_version_id_asset_versions",
            type_="foreignkey",
        )
        batch_op.drop_constraint("fk_designs_model_asset_id_model_assets", type_="foreignkey")
        batch_op.drop_column("base_asset_version_id")
        batch_op.alter_column(
            "model_asset_id",
            existing_type=sa.String(length=64),
            nullable=False,
        )
        batch_op.create_foreign_key(
            "fk_designs_model_asset_id_model_assets",
            "model_assets",
            ["model_asset_id"],
            ["id"],
        )


def _drop_foreign_keys(table_name: str, columns: list[str], referred_table: str) -> None:
    inspector = sa.inspect(op.get_bind())
    for foreign_key in inspector.get_foreign_keys(table_name):
        if (
            foreign_key.get("constrained_columns") == columns
            and foreign_key.get("referred_table") == referred_table
            and foreign_key.get("name")
        ):
            op.drop_constraint(foreign_key["name"], table_name, type_="foreignkey")


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"
