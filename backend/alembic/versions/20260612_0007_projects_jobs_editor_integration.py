"""Add projects, jobs, and editor integration fields.

Revision ID: 20260612_0007
Revises: 20260528_0006
Create Date: 2026-06-12
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "20260612_0007"
down_revision: str | None = "20260528_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="scan"),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_source_type", "projects", ["source_type"])
    op.create_index("ix_projects_status", "projects", ["status"])
    op.create_index("ix_projects_user_id", "projects", ["user_id"])

    with op.batch_alter_table("scan_sessions") as batch_op:
        batch_op.add_column(sa.Column("project_id", sa.String(length=64), nullable=True))
        batch_op.create_foreign_key(
            "fk_scan_sessions_project_id_projects",
            "projects",
            ["project_id"],
            ["id"],
        )
        batch_op.create_index("ix_scan_sessions_project_id", ["project_id"])

    with op.batch_alter_table("designs") as batch_op:
        batch_op.add_column(sa.Column("project_id", sa.String(length=64), nullable=True))
        batch_op.create_foreign_key(
            "fk_designs_project_id_projects",
            "projects",
            ["project_id"],
            ["id"],
        )
        batch_op.create_index("ix_designs_project_id", ["project_id"])

    op.add_column(
        "model_assets",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ready"),
    )
    op.add_column(
        "model_assets",
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="scan"),
    )
    op.create_index("ix_model_assets_status", "model_assets", ["status"])
    op.create_index("ix_model_assets_source_type", "model_assets", ["source_type"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=True),
        sa.Column("design_id", sa.String(length=64), nullable=True),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("rq_job_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["design_id"], ["designs.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jobs_design_id", "jobs", ["design_id"])
    op.create_index("ix_jobs_project_id", "jobs", ["project_id"])
    op.create_index("ix_jobs_rq_job_id", "jobs", ["rq_job_id"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_type", "jobs", ["type"])
    op.create_index("ix_jobs_user_id", "jobs", ["user_id"])

    _backfill_projects()


def downgrade() -> None:
    op.drop_index("ix_jobs_user_id", table_name="jobs")
    op.drop_index("ix_jobs_type", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_index("ix_jobs_rq_job_id", table_name="jobs")
    op.drop_index("ix_jobs_project_id", table_name="jobs")
    op.drop_index("ix_jobs_design_id", table_name="jobs")
    op.drop_table("jobs")

    op.drop_index("ix_model_assets_source_type", table_name="model_assets")
    op.drop_index("ix_model_assets_status", table_name="model_assets")
    op.drop_column("model_assets", "source_type")
    op.drop_column("model_assets", "status")

    with op.batch_alter_table("designs") as batch_op:
        batch_op.drop_index("ix_designs_project_id")
        batch_op.drop_constraint("fk_designs_project_id_projects", type_="foreignkey")
        batch_op.drop_column("project_id")

    with op.batch_alter_table("scan_sessions") as batch_op:
        batch_op.drop_index("ix_scan_sessions_project_id")
        batch_op.drop_constraint("fk_scan_sessions_project_id_projects", type_="foreignkey")
        batch_op.drop_column("project_id")

    op.drop_index("ix_projects_user_id", table_name="projects")
    op.drop_index("ix_projects_status", table_name="projects")
    op.drop_index("ix_projects_source_type", table_name="projects")
    op.drop_table("projects")


def _backfill_projects() -> None:
    conn = op.get_bind()
    scan_rows = conn.execute(
        sa.text(
            """
            SELECT id, user_id, source_type, import_name, created_at, updated_at
            FROM scan_sessions
            WHERE project_id IS NULL
            """
        )
    ).mappings()
    now = datetime.utcnow()
    project_id_by_scan_id: dict[str, str] = {}

    for row in scan_rows:
        project_id = f"proj_{uuid4().hex}"
        source_type = "uploaded_glb" if row["source_type"] == "import" else "scan"
        project_name = row["import_name"] or "Untitled shoe project"
        created_at = row["created_at"] or now
        updated_at = row["updated_at"] or created_at
        conn.execute(
            sa.text(
                """
                INSERT INTO projects
                    (id, user_id, name, status, source_type, thumbnail_url, created_at, updated_at)
                VALUES
                    (:id, :user_id, :name, :status, :source_type, NULL, :created_at, :updated_at)
                """
            ),
            {
                "id": project_id,
                "user_id": row["user_id"],
                "name": project_name,
                "status": "ready",
                "source_type": source_type,
                "created_at": created_at,
                "updated_at": updated_at,
            },
        )
        conn.execute(
            sa.text("UPDATE scan_sessions SET project_id = :project_id WHERE id = :scan_id"),
            {"project_id": project_id, "scan_id": row["id"]},
        )
        project_id_by_scan_id[row["id"]] = project_id

    asset_rows = conn.execute(
        sa.text("SELECT id, scan_session_id FROM model_assets")
    ).mappings()
    project_id_by_asset_id: dict[str, str] = {}
    for row in asset_rows:
        project_id = project_id_by_scan_id.get(row["scan_session_id"])
        if project_id:
            project_id_by_asset_id[row["id"]] = project_id
        source_type = "scan"
        scan_source = conn.execute(
            sa.text("SELECT source_type FROM scan_sessions WHERE id = :scan_id"),
            {"scan_id": row["scan_session_id"]},
        ).scalar()
        if scan_source == "import":
            source_type = "uploaded_glb"
        conn.execute(
            sa.text(
                """
                UPDATE model_assets
                SET status = 'ready', source_type = :source_type
                WHERE id = :asset_id
                """
            ),
            {"asset_id": row["id"], "source_type": source_type},
        )

    design_rows = conn.execute(sa.text("SELECT id, model_asset_id FROM designs")).mappings()
    for row in design_rows:
        project_id = project_id_by_asset_id.get(row["model_asset_id"])
        if project_id:
            conn.execute(
                sa.text("UPDATE designs SET project_id = :project_id WHERE id = :design_id"),
                {"project_id": project_id, "design_id": row["id"]},
            )
