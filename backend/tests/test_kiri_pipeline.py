from __future__ import annotations

import io
import zipfile
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException, status
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import create_kiri_preview_ticket, decode_kiri_preview_ticket
from app.db.database import Base
from app.models import KiriScanTask, KiriTaskStatus, Project, ScanSession, ScanStatus, User
from app.schemas.scan import CropBox
from app.services.kiri_client import KiriApiClient, KiriError
from app.services.kiri_pipeline import KiriPipelineService
from app.services.command_runner import CommandResult
from app.services.crop_baker import CropBakeService
from app.services.mesh_cleanup import MeshCleanupReport
from app.services.scan_sessions import ScanSessionService
from app.services.storage import StoredObject, checksum_bytes


def kiri_settings(**overrides) -> Settings:
    values = {
        "kiri_api_token": "secret-token",
        "kiri_api_base_url": "https://api.kiriengine.app/api",
        "kiri_download_allowed_hosts": ["kiriengine.app"],
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_kiri_client_uploads_glb_request_with_backend_token(tmp_path) -> None:
    video = tmp_path / "scan.mp4"
    video.write_bytes(b"video")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer secret-token"
        assert request.url.path == "/api/v1/open/photo/video"
        assert b'name="fileFormat"' in request.read()
        return httpx.Response(200, json={"code": 0, "data": {"serialize": "serial-1"}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    service = KiriApiClient(client=client, settings=kiri_settings())

    assert service.upload_video(video) == "serial-1"


def test_kiri_client_rejects_non_allowlisted_download_host() -> None:
    service = KiriApiClient(settings=kiri_settings())

    with pytest.raises(KiriError, match="allowlisted"):
        service.download_model_zip("https://attacker.example/model.zip")


def test_crop_box_rejects_invalid_normalized_size() -> None:
    with pytest.raises(ValueError):
        CropBox.model_validate(
            {
                "center": {"x": 0, "y": 0, "z": 0},
                "size": {"x": 0, "y": 1, "z": 1},
            }
        )


def test_preview_ticket_is_scoped_to_scan_session() -> None:
    ticket = create_kiri_preview_ticket("scan_123")

    assert decode_kiri_preview_ticket(ticket) == "scan_123"


def test_crop_baker_passes_absolute_paths_to_blender(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "source.glb"
    source.write_bytes(b"glTF")
    runner = CaptureCropRunner()
    service = CropBakeService(blender=FakeBlender(), runner=runner)

    service.bake(Path("source.glb"), Path("output/cropped.glb"), CropBox())

    assert all(Path(value).is_absolute() for value in runner.command[-3:])


def test_successful_kiri_status_downloads_glb_before_marking_ready() -> None:
    with database_session() as db:
        task = create_task(db)
        storage = MemoryStorage()
        service = KiriPipelineService(
            db,
            api=FakeKiriApi("successful", model_zip()),
            storage=storage,
            crop_baker=object(),
            mesh_cleanup=object(),
        )

        refreshed = service.refresh(task)

        assert refreshed.status == KiriTaskStatus.READY_FOR_CROP
        assert refreshed.scan_session.status == ScanStatus.KIRI_READY
        assert refreshed.source_glb_path == f"kiri/{refreshed.scan_session_id}/source.glb"
        assert storage.get_bytes(refreshed.source_glb_path).startswith(b"glTF")


def test_failed_kiri_status_marks_scan_and_project_failed() -> None:
    with database_session() as db:
        task = create_task(db)
        service = KiriPipelineService(
            db,
            api=FakeKiriApi("failed", b""),
            storage=MemoryStorage(),
            crop_baker=object(),
            mesh_cleanup=object(),
        )

        refreshed = service.refresh(task)

        assert refreshed.status == KiriTaskStatus.FAILED
        assert refreshed.scan_session.status == ScanStatus.FAILED
        assert refreshed.scan_session.project.status == "failed"


def test_transient_kiri_error_keeps_task_retryable() -> None:
    with database_session() as db:
        task = create_task(db)
        service = KiriPipelineService(
            db,
            api=FailingKiriApi(),
            storage=MemoryStorage(),
            crop_baker=object(),
            mesh_cleanup=object(),
        )

        refreshed = service.refresh(task)

        assert refreshed.status == KiriTaskStatus.PROCESSING
        assert "temporarily unavailable" in refreshed.error_message


def test_save_project_bakes_crop_and_creates_canonical_model_asset() -> None:
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
            api=FakeKiriApi("successful", model_zip()),
            storage=storage,
            crop_baker=crop_baker,
            mesh_cleanup=FakeMeshCleanup(),
        )

        service.bake_saved_project(task.scan_session_id)

        db.refresh(task)
        assert task.status == KiriTaskStatus.READY
        assert task.scan_session.status == ScanStatus.CROP_READY
        assert task.scan_session.model_asset is not None
        assert storage.exists(f"models/{task.scan_session_id}/shoe_preview.glb")
        assert crop_baker.calls == 1


def test_scan_session_ownership_is_required_for_kiri_routes() -> None:
    with database_session() as db:
        task = create_task(db)
        stranger = User(name="Stranger", email="stranger@example.com")
        db.add(stranger)
        db.commit()

        with pytest.raises(HTTPException) as exc:
            ScanSessionService(db).get_for_user(task.scan_session_id, stranger)

        assert exc.value.status_code == status.HTTP_404_NOT_FOUND


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


def model_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("result/model.glb", b"glTF" + b"\x00" * 16)
    return buffer.getvalue()


class FakeKiriApi:
    def __init__(self, provider_status: str, zip_bytes: bytes) -> None:
        self.provider_status = provider_status
        self.zip_bytes = zip_bytes

    def get_status(self, _serialize: str) -> str:
        return self.provider_status

    def get_model_zip_url(self, _serialize: str) -> str:
        return "https://assets.kiriengine.app/model.zip"

    def download_model_zip(self, _model_url: str) -> bytes:
        return self.zip_bytes


class FailingKiriApi:
    def get_status(self, _serialize: str) -> str:
        raise KiriError("Kiri is temporarily unavailable.")


class FakeCropBaker:
    def __init__(self) -> None:
        self.calls = 0

    def bake(self, source_glb, output_glb, crop_box) -> None:
        self.calls += 1
        assert source_glb.read_bytes().startswith(b"glTF")
        assert crop_box.coordinate_space == "normalized"
        output_glb.write_bytes(source_glb.read_bytes())


class FakeBlender:
    def require_available(self) -> str:
        return "blender"


class CaptureCropRunner:
    def __init__(self) -> None:
        self.command: list[str] = []

    def run(self, command, **_kwargs) -> CommandResult:
        self.command = command
        Path(command[-2]).write_bytes(b"glTF")
        return CommandResult(command=command, return_code=0, stdout="", stderr="")


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

    def local_path(self, key: str):
        return None
