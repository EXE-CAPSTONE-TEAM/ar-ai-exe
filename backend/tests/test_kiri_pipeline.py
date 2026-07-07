from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

pytest.importorskip("app.services.kiri_pipeline")

from app.db.database import Base  # noqa: E402
from app.models import (  # noqa: E402
    AssetVersionType,
    KiriScanTask,
    KiriTaskStatus,
    Project,
    ScanSession,
    ScanStatus,
    User,
)
from app.schemas.scan import CropBox  # noqa: E402
from app.services.asset_versions import AssetVersionService  # noqa: E402
from app.services.kiri_pipeline import KiriPipelineService  # noqa: E402
from app.services.mesh_cleanup import MeshCleanupReport  # noqa: E402
from app.services.storage import StoredObject, checksum_bytes  # noqa: E402


def test_save_project_bakes_crop_and_creates_project_scoped_model_asset_storage() -> None:
    with database_session() as db:
        task = create_task(db)
        storage = MemoryStorage()
        source_key = f"kiri/{task.scan_session_id}/source.glb"
        storage.put_bytes(source_key, b"glTF" + b"\x00" * 16, "model/gltf-binary")
        task.source_glb_path = source_key
        task.crop_box_json = CropBox().model_dump_json(by_alias=True)
        task.status = KiriTaskStatus.CROP_BAKING
        task.scan_session.status = ScanStatus.CROP_BAKING
        db.commit()
        crop_baker = FakeCropBaker()
        service = KiriPipelineService(
            db,
            api=object(),
            storage=storage,
            crop_baker=crop_baker,
            mesh_cleanup=FakeMeshCleanup(),
        )

        service.bake_saved_project(task.scan_session_id)

        db.refresh(task)
        version = AssetVersionService(db).latest_published(
            task.scan_session.project_id,
            AssetVersionType.MODEL,
        )
        assert version is not None
        assert task.status == KiriTaskStatus.READY
        assert task.scan_session.status == ScanStatus.CROP_READY
        assert task.scan_session.model_asset is not None
        assert crop_baker.calls == 1
        assert all(
            item.storage_key.startswith(
                f"projects/{task.scan_session.project_id}/assets/model/primary/versions/{version.id}/"
            )
            for item in version.files
        )
        assert not storage.exists(f"models/{task.scan_session_id}/shoe_preview.glb")


class database_session:
    def __enter__(self) -> Session:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        return self.session

    def __exit__(self, *_args) -> None:
        self.session.close()
        self.engine.dispose()


def create_task(db: Session) -> KiriScanTask:
    user = User(name="Owner", email="owner@example.com")
    project = Project(user=user, name="Kiri scan")
    scan = ScanSession(user=user, project=project, status=ScanStatus.KIRI_PROCESSING)
    task = KiriScanTask(
        scan_session=scan,
        provider_serialize="serial-1",
        provider_status="processing",
        status=KiriTaskStatus.PROCESSING,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


class FakeCropBaker:
    def __init__(self) -> None:
        self.calls = 0

    def bake(self, source_glb, output_glb, crop_box) -> None:
        self.calls += 1
        assert source_glb.read_bytes().startswith(b"glTF")
        assert crop_box.coordinate_space == "normalized"
        output_glb.write_bytes(source_glb.read_bytes())


class FakeMeshCleanup:
    def cleanup(self, source_model, output_dir, **_kwargs) -> MeshCleanupReport:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "shoe_preview.glb").write_bytes(source_model.read_bytes())
        (output_dir / "shoe.obj").write_text("o shoe\n", encoding="utf-8")
        (output_dir / "shoe.mtl").write_text("newmtl shoe\n", encoding="utf-8")
        (output_dir / "shoe_texture.png").write_bytes(b"png")
        return MeshCleanupReport.from_payload(
            {
                "editorReady": True,
                "editorReadyScore": 95,
                "meshObjectCount": 1,
                "boundingBox": {"after": {"maxDimension": 2.4}},
                "normalizedScale": 1,
                "triangleCountBefore": 100,
                "triangleCountAfter": 80,
                "cleanupWarnings": [],
            }
        )


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_bytes(self, key: str, data: bytes, content_type: str) -> StoredObject:
        self.objects[key] = data
        return StoredObject(key, len(data), content_type, checksum_bytes(data))

    def get_bytes(self, key: str) -> bytes:
        return self.objects[key]

    def exists(self, key: str) -> bool:
        return key in self.objects

    def create_signed_url(self, key: str, expires_in: int = 300) -> str | None:
        return None

    def local_path(self, key: str) -> Path | None:
        return None
