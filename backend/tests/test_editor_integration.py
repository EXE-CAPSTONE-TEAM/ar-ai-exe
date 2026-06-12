import json
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.models import (
    AssetStatus,
    Design,
    DesignPreviewStatus,
    Job,
    JobStatus,
    JobType,
    ModelAsset,
    Project,
    ProjectSourceType,
    ProjectStatus,
    ScanSession,
    User,
)
from app.services.jobs import run_job
from app.services.projects import ProjectService


class FakeStorage:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects

    def get_bytes(self, key: str) -> bytes:
        return self.objects[key]

    def exists(self, key: str) -> bool:
        return key in self.objects


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_editor_context_returns_project_model_and_latest_design(monkeypatch) -> None:
    storage = FakeStorage(
        {
            "models/model_001/quality_report.json": b"{}",
            "designs/design_001/design_config.json": json.dumps(
                {
                    "modelAssetId": "model_001",
                    "baseColor": "#ffffff",
                    "material": {"roughness": 1, "metallic": 0},
                    "stickers": [],
                    "texts": [],
                }
            ).encode("utf-8"),
        }
    )
    monkeypatch.setattr("app.services.model_assets.get_storage_service", lambda: storage)
    monkeypatch.setattr("app.services.designs.get_storage_service", lambda: storage)

    db = make_session()
    user = User(id="user_001", name="Demo", email="demo@example.com")
    project = Project(
        id="proj_001",
        user_id=user.id,
        name="Demo project",
        status=ProjectStatus.READY,
        source_type=ProjectSourceType.UPLOADED_GLB,
    )
    scan = ScanSession(
        id="scan_001",
        user_id=user.id,
        project_id=project.id,
        status="completed",
        source_type="import",
    )
    asset = ModelAsset(
        id="model_001",
        scan_session_id=scan.id,
        status=AssetStatus.READY,
        source_type=ProjectSourceType.UPLOADED_GLB,
        glb_path="models/model_001/shoe_preview.glb",
        obj_path="models/model_001/shoe.obj",
        mtl_path="models/model_001/shoe.mtl",
        texture_path="models/model_001/shoe_texture.png",
        quality_report_path="models/model_001/quality_report.json",
    )
    design = Design(
        id="design_001",
        user_id=user.id,
        project_id=project.id,
        model_asset_id=asset.id,
        name="Latest draft",
        design_config_path="designs/design_001/design_config.json",
        status="draft",
        preview_status=DesignPreviewStatus.PENDING,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add_all([user, project, scan, asset, design])
    db.commit()

    context = ProjectService(db).editor_context(project.id, user)

    assert context.project.id == "proj_001"
    assert context.model_asset is not None
    assert context.model_asset.canonical_glb_url == "/api/models/model_001/download/glb"
    assert context.latest_design is not None
    assert context.latest_design.id == "design_001"
    assert context.permissions.can_edit is True


def test_run_job_marks_bake_job_completed(monkeypatch) -> None:
    db = make_session()
    user = User(id="user_001", name="Demo", email="demo@example.com")
    design = Design(
        id="design_001",
        user_id=user.id,
        project_id="proj_001",
        model_asset_id="model_001",
        name="Draft",
        design_config_path="designs/design_001/design_config.json",
        status="draft",
        preview_status=DesignPreviewStatus.PENDING,
    )
    job = Job(
        id="job_001",
        user_id=user.id,
        project_id="proj_001",
        design_id=design.id,
        type=JobType.BAKE,
        status=JobStatus.QUEUED,
        progress=0,
    )
    db.add_all([user, design, job])
    db.commit()
    job_id = job.id

    monkeypatch.setattr("app.services.jobs.SessionLocal", lambda: db)

    def mark_ready(_service, design_to_refresh: Design) -> None:
        design_to_refresh.preview_status = DesignPreviewStatus.READY
        db.commit()

    monkeypatch.setattr("app.services.jobs.DesignService.refresh_preview", mark_ready)

    run_job(job_id)
    updated_job = db.get(Job, job_id)

    assert updated_job is not None
    assert updated_job.status == JobStatus.COMPLETED
    assert updated_job.progress == 100
