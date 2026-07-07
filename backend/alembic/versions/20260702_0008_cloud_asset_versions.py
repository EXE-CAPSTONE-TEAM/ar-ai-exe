"""Add project-owned immutable asset versions and file manifests.

Revision ID: 20260702_0008
Revises: 20260612_0007
Create Date: 2026-07-02
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "20260702_0008"
down_revision: str | None = "20260612_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CANONICAL_FILES = (
    ("glb", "shoe_preview.glb", "glb_path", "glb_content_type", "glb_size_bytes", "glb_checksum", "model/gltf-binary"),
    ("obj", "shoe.obj", "obj_path", "obj_content_type", "obj_size_bytes", "obj_checksum", "text/plain"),
    ("mtl", "shoe.mtl", "mtl_path", "mtl_content_type", "mtl_size_bytes", "mtl_checksum", "text/plain"),
    ("texture", "shoe_texture.png", "texture_path", "texture_content_type", "texture_size_bytes", "texture_checksum", "image/png"),
    ("metadata", "metadata.json", "metadata_path", "metadata_content_type", "metadata_size_bytes", "metadata_checksum", "application/json"),
    (
        "quality-report",
        "quality_report.json",
        "quality_report_path",
        "quality_report_content_type",
        "quality_report_size_bytes",
        "quality_report_checksum",
        "application/json",
    ),
    (
        "obj-package",
        "shoe_obj_package.zip",
        "obj_package_zip_path",
        "obj_package_zip_content_type",
        "obj_package_zip_size_bytes",
        "obj_package_zip_checksum",
        "application/zip",
    ),
)


def upgrade() -> None:
    op.create_table(
        "asset_versions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("logical_key", sa.String(length=120), nullable=False, server_default="primary"),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ready"),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="generated"),
        # Reserved for future asset lineage such as model -> preview -> export.
        sa.Column("parent_asset_version_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["parent_asset_version_id"], ["asset_versions.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "asset_type",
            "logical_key",
            "version_number",
            name="uq_asset_versions_project_type_key_number",
        ),
    )
    op.create_index("ix_asset_versions_project_id", "asset_versions", ["project_id"])
    op.create_index("ix_asset_versions_asset_type", "asset_versions", ["asset_type"])
    op.create_index("ix_asset_versions_logical_key", "asset_versions", ["logical_key"])
    op.create_index("ix_asset_versions_status", "asset_versions", ["status"])
    op.create_index("ix_asset_versions_source_type", "asset_versions", ["source_type"])
    op.create_index(
        "ix_asset_versions_parent_asset_version_id",
        "asset_versions",
        ["parent_asset_version_id"],
    )
    op.create_index(
        "ix_asset_versions_project_type_created",
        "asset_versions",
        ["project_id", "asset_type", "created_at"],
    )

    op.create_table(
        "asset_version_files",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("asset_version_id", sa.String(length=64), nullable=False),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column("canonical_name", sa.String(length=180), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["asset_version_id"], ["asset_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "asset_version_id",
            "file_type",
            name="uq_asset_version_files_version_type",
        ),
    )
    op.create_index(
        "ix_asset_version_files_asset_version_id",
        "asset_version_files",
        ["asset_version_id"],
    )
    op.create_index("ix_asset_version_files_file_type", "asset_version_files", ["file_type"])

    op.create_table(
        "asset_version_legacy_links",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("asset_version_id", sa.String(length=64), nullable=False),
        sa.Column("legacy_type", sa.String(length=32), nullable=False),
        sa.Column("legacy_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["asset_version_id"], ["asset_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "legacy_type",
            "legacy_id",
            "asset_version_id",
            name="uq_asset_version_legacy_links_identity",
        ),
    )
    op.create_index(
        "ix_asset_version_legacy_links_asset_version_id",
        "asset_version_legacy_links",
        ["asset_version_id"],
    )
    op.create_index(
        "ix_asset_version_legacy_links_legacy_type",
        "asset_version_legacy_links",
        ["legacy_type"],
    )
    op.create_index(
        "ix_asset_version_legacy_links_legacy_id",
        "asset_version_legacy_links",
        ["legacy_id"],
    )

    _backfill_model_versions()


def downgrade() -> None:
    op.drop_index("ix_asset_version_legacy_links_legacy_id", table_name="asset_version_legacy_links")
    op.drop_index("ix_asset_version_legacy_links_legacy_type", table_name="asset_version_legacy_links")
    op.drop_index(
        "ix_asset_version_legacy_links_asset_version_id",
        table_name="asset_version_legacy_links",
    )
    op.drop_table("asset_version_legacy_links")

    op.drop_index("ix_asset_version_files_file_type", table_name="asset_version_files")
    op.drop_index("ix_asset_version_files_asset_version_id", table_name="asset_version_files")
    op.drop_table("asset_version_files")

    op.drop_index("ix_asset_versions_project_type_created", table_name="asset_versions")
    op.drop_index("ix_asset_versions_parent_asset_version_id", table_name="asset_versions")
    op.drop_index("ix_asset_versions_source_type", table_name="asset_versions")
    op.drop_index("ix_asset_versions_status", table_name="asset_versions")
    op.drop_index("ix_asset_versions_logical_key", table_name="asset_versions")
    op.drop_index("ix_asset_versions_asset_type", table_name="asset_versions")
    op.drop_index("ix_asset_versions_project_id", table_name="asset_versions")
    op.drop_table("asset_versions")


def _backfill_model_versions() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            """
            SELECT
                ma.*,
                ss.project_id AS resolved_project_id
            FROM model_assets ma
            JOIN scan_sessions ss ON ss.id = ma.scan_session_id
            WHERE ss.project_id IS NOT NULL
            ORDER BY ss.project_id, ma.created_at, ma.id
            """
        )
    ).mappings()
    next_version_by_project: dict[str, int] = {}

    for row in rows:
        project_id = row["resolved_project_id"]
        version_number = next_version_by_project.get(project_id, 0) + 1
        next_version_by_project[project_id] = version_number
        asset_version_id = f"assetv_{uuid4().hex}"
        created_at = row["created_at"]

        conn.execute(
            sa.text(
                """
                INSERT INTO asset_versions
                    (id, project_id, asset_type, logical_key, version_number, status,
                     source_type, parent_asset_version_id, created_at)
                VALUES
                    (:id, :project_id, 'model', 'primary', :version_number, :status,
                     :source_type, NULL, :created_at)
                """
            ),
            {
                "id": asset_version_id,
                "project_id": project_id,
                "version_number": version_number,
                "status": row["status"] or "ready",
                "source_type": row["source_type"] or "scan",
                "created_at": created_at,
            },
        )

        # Legacy storage keys are intentionally kept as-is and are not moved or copied.
        # New asset versions created after this migration should use version-scoped project keys.
        for file_type, canonical_name, key_col, type_col, size_col, checksum_col, default_type in CANONICAL_FILES:
            storage_key = row[key_col]
            if not storage_key:
                continue
            conn.execute(
                sa.text(
                    """
                    INSERT INTO asset_version_files
                        (id, asset_version_id, file_type, canonical_name, storage_key,
                         content_type, size_bytes, checksum, created_at)
                    VALUES
                        (:id, :asset_version_id, :file_type, :canonical_name, :storage_key,
                         :content_type, :size_bytes, :checksum, :created_at)
                    """
                ),
                {
                    "id": f"assetfile_{uuid4().hex}",
                    "asset_version_id": asset_version_id,
                    "file_type": file_type,
                    "canonical_name": canonical_name,
                    "storage_key": storage_key,
                    "content_type": row[type_col] or default_type,
                    "size_bytes": row[size_col],
                    "checksum": row[checksum_col],
                    "created_at": created_at,
                },
            )

        conn.execute(
            sa.text(
                """
                INSERT INTO asset_version_legacy_links
                    (id, asset_version_id, legacy_type, legacy_id, created_at)
                VALUES
                    (:id, :asset_version_id, 'model_asset', :legacy_id, :created_at)
                """
            ),
            {
                "id": f"assetlink_{uuid4().hex}",
                "asset_version_id": asset_version_id,
                "legacy_id": row["id"],
                "created_at": created_at,
            },
        )
