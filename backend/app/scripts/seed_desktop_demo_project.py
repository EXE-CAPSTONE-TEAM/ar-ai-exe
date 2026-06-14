from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from pathlib import Path

from sqlalchemy import select

from app.db.database import Base, SessionLocal, engine
from app.models import (
    AssetStatus,
    Design,
    DesignPreviewStatus,
    DesignStatus,
    ExportPackage,
    Job,
    ModelAsset,
    Project,
    ProjectSourceType,
    ProjectStatus,
    ScanSession,
    ScanSource,
    ScanStatus,
)
from app.services.model_assets import ModelAssetFiles, ModelAssetService
from app.services.storage import get_storage_service
from app.services.users import UserService


DEMO_PROJECT_ID = "proj_desktop_demo"
DEMO_SCAN_ID = "scan_desktop_demo"
DEMO_DESIGN_ID = "design_desktop_demo"


def main() -> None:
    args = parse_args()
    result = seed_demo_project(model_path=args.model, name=args.name, force=args.force)
    print(json.dumps(result, indent=2))


def seed_demo_project(
    model_path: Path,
    name: str = "KusShoes Desktop Demo",
    force: bool = False,
) -> dict[str, str]:
    model_path = model_path.resolve()
    if not model_path.is_file():
        raise SystemExit(f"Model file not found: {model_path}")

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        user = UserService(db).get_or_create_demo_user()

        project = upsert_project(db, user.id, name)
        scan = upsert_scan(db, user.id, project.id, name)
        existing_asset = db.scalar(select(ModelAsset).where(ModelAsset.scan_session_id == scan.id))
        existing_design = db.get(Design, DEMO_DESIGN_ID)
        if existing_asset and existing_design and not force:
            return {
                "projectId": project.id,
                "scanSessionId": scan.id,
                "modelAssetId": existing_asset.id,
                "designId": existing_design.id,
                "sourceModel": str(model_path),
                "openUrl": f"/?desktop=1&projectId={project.id}",
            }

        clear_previous_demo_records(db, project.id, scan.id)

        with tempfile.TemporaryDirectory() as temp_dir_name:
            files = create_model_asset_files(Path(temp_dir_name), model_path, name)
            asset = ModelAssetService(db).create_from_files(
                scan_session_id=scan.id,
                files=files,
                storage_prefix=f"models/{scan.id}",
                source_type=ProjectSourceType.TEMPLATE,
            )
            asset.status = AssetStatus.READY
            project.status = ProjectStatus.READY
            db.commit()
            db.refresh(asset)

        design = create_demo_design(db, user.id, project.id, asset.id, name)
        db.commit()

        return {
            "projectId": project.id,
            "scanSessionId": scan.id,
            "modelAssetId": asset.id,
            "designId": design.id,
            "sourceModel": str(model_path),
            "openUrl": f"/?desktop=1&projectId={project.id}",
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed the local desktop demo project.")
    parser.add_argument(
        "--model",
        type=Path,
        default=Path("../data/3DModel.glb"),
        help="Path to the GLB file used for the demo project.",
    )
    parser.add_argument("--name", default="KusShoes Desktop Demo", help="Demo project name.")
    parser.add_argument("--force", action="store_true", help="Reset existing demo project records.")
    return parser.parse_args()


def upsert_project(db, user_id: str, name: str) -> Project:
    project = db.get(Project, DEMO_PROJECT_ID)
    if project is None:
        project = Project(
            id=DEMO_PROJECT_ID,
            user_id=user_id,
            name=name,
            status=ProjectStatus.READY,
            source_type=ProjectSourceType.TEMPLATE,
        )
        db.add(project)
    else:
        project.user_id = user_id
        project.name = name
        project.status = ProjectStatus.READY
        project.source_type = ProjectSourceType.TEMPLATE
    db.commit()
    db.refresh(project)
    return project


def upsert_scan(db, user_id: str, project_id: str, name: str) -> ScanSession:
    scan = db.get(ScanSession, DEMO_SCAN_ID)
    if scan is None:
        scan = ScanSession(
            id=DEMO_SCAN_ID,
            user_id=user_id,
            project_id=project_id,
            status=ScanStatus.COMPLETED,
            source_type=ScanSource.IMPORT,
            import_name=name,
        )
        db.add(scan)
    else:
        scan.user_id = user_id
        scan.project_id = project_id
        scan.status = ScanStatus.COMPLETED
        scan.source_type = ScanSource.IMPORT
        scan.import_name = name
    db.commit()
    db.refresh(scan)
    return scan


def clear_previous_demo_records(db, project_id: str, scan_id: str) -> None:
    demo_designs = db.scalars(select(Design).where(Design.project_id == project_id)).all()
    for design in demo_designs:
        for export_package in db.scalars(select(ExportPackage).where(ExportPackage.design_id == design.id)).all():
            db.delete(export_package)
        db.delete(design)

    for job in db.scalars(select(Job).where(Job.project_id == project_id)).all():
        db.delete(job)

    existing_asset = db.scalar(select(ModelAsset).where(ModelAsset.scan_session_id == scan_id))
    if existing_asset:
        db.delete(existing_asset)
    db.commit()


def create_demo_design(db, user_id: str, project_id: str, model_asset_id: str, name: str) -> Design:
    config_payload = {
        "modelAssetId": model_asset_id,
        "baseColor": "#ffffff",
        "material": {"roughness": 1, "metallic": 0},
        "stickers": [],
        "texts": [],
        "camera": {},
        "metadata": {"editorVersion": "1.0.0", "demo": True},
    }
    storage = get_storage_service()
    config_object = storage.put_bytes(
        f"designs/{DEMO_DESIGN_ID}/design_config.json",
        json.dumps(config_payload, indent=2).encode("utf-8"),
        "application/json",
    )
    design = Design(
        id=DEMO_DESIGN_ID,
        user_id=user_id,
        project_id=project_id,
        model_asset_id=model_asset_id,
        name=f"{name} Draft",
        design_config_path=config_object.key,
        status=DesignStatus.DRAFT,
        preview_status=DesignPreviewStatus.NONE,
    )
    db.add(design)
    return design


def create_model_asset_files(temp_dir: Path, glb_path: Path, name: str) -> ModelAssetFiles:
    glb = temp_dir / "shoe_preview.glb"
    obj = temp_dir / "shoe.obj"
    mtl = temp_dir / "shoe.mtl"
    texture = temp_dir / "shoe_texture.png"
    metadata = temp_dir / "metadata.json"
    quality_report = temp_dir / "quality_report.json"
    obj_package_zip = temp_dir / "shoe_obj_package.zip"

    glb.write_bytes(glb_path.read_bytes())
    obj.write_text("# Demo GLB project does not include OBJ geometry.\n", encoding="utf-8")
    mtl.write_text("newmtl demo_material\nKd 1.0 1.0 1.0\n", encoding="utf-8")
    texture.write_bytes(
        bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
            "0000000d49444154789c6360f8ffff3f0005fe02fea7a60d1f0000000049454e44ae426082"
        )
    )
    metadata.write_text(
        json.dumps(
            {
                "name": name,
                "source": "desktop-demo",
                "sourceModel": str(glb_path),
                "format": "glb",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    quality_report.write_text(
        json.dumps(
            {
                "status": "ready",
                "source": "desktop-demo",
                "notes": ["Seeded from data/3DModel.glb for local desktop review."],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    with zipfile.ZipFile(obj_package_zip, "w", zipfile.ZIP_DEFLATED) as package:
        package.write(obj, "shoe.obj")
        package.write(mtl, "shoe.mtl")
        package.write(texture, "shoe_texture.png")

    return ModelAssetFiles(
        glb=glb,
        obj=obj,
        mtl=mtl,
        texture=texture,
        metadata=metadata,
        quality_report=quality_report,
        obj_package_zip=obj_package_zip,
    )


if __name__ == "__main__":
    main()
