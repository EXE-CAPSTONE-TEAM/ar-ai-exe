from __future__ import annotations

import io
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import HTTPException, status
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import create_kiri_preview_ticket, decode_kiri_preview_ticket
from app.db.database import Base
from app.models import (
    KiriScanTask,
    KiriTaskStatus,
    Project,
    ScanSession,
    ScanStatus,
    User,
)
from app.schemas.scan import CropBox
from app.services.command_runner import CommandResult
from app.services.control_plane_mobile import ControlPlanePublishResult
from app.services.crop_baker import CropBakeService
from app.services.kiri_client import KiriApiClient, KiriError
from app.services.kiri_pipeline import KiriPipelineService
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
        )

        refreshed = service.refresh(task)

        assert refreshed.status == KiriTaskStatus.READY_FOR_CROP
        assert refreshed.scan_session.status == ScanStatus.KIRI_READY
        assert refreshed.source_glb_path == f"kiri/{refreshed.scan_session_id}/source.glb"
        assert not any("zip" in k or "video" in k for k in storage.get_bytes_calls)
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


def test_publish_saved_project_publishes_raw_glb_to_control_plane() -> None:
    with database_session() as db:
        scan = ScanSession(
            status=ScanStatus.KIRI_READY,
            control_plane_user_id="cp-user-1",
            control_plane_project_id="cp-proj-1",
            control_plane_project_name="Sneaker Scan",
            control_plane_completion_token="complete-token-1",
            web_design_url="https://kusshoes.vn/projects/cp-proj-1",
        )
        db.add(scan)
        db.commit()
        db.refresh(scan)

        task = KiriScanTask(
            scan_session=scan,
            provider_serialize="serial-1",
            provider_status="successful",
            status=KiriTaskStatus.READY_FOR_CROP,
            source_glb_path=f"kiri/{scan.id}/source.glb",
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        storage = MemoryStorage()
        glb_data = b"glTF" + b"\x00" * 28
        storage.put_bytes(task.source_glb_path, glb_data, "model/gltf-binary")

        cp_client = FakeControlPlaneClient(status="raw")
        service = KiriPipelineService(
            db,
            api=FakeKiriApi("successful", model_zip()),
            storage=storage,
            control_plane=cp_client,
        )

        service.publish_saved_project(scan.id)

        db.refresh(task)
        db.refresh(scan)

        assert task.status == KiriTaskStatus.READY
        assert scan.status == ScanStatus.CROP_READY
        assert scan.control_plane_model_asset_id == "asset-control-plane-1"
        assert scan.control_plane_published_at is not None
        assert b"".join(cp_client.published_chunks) == glb_data
        assert cp_client.call_args["file_size_bytes"] == len(glb_data)


def test_publish_saved_project_creates_local_model_asset() -> None:
    with database_session() as db:
        task = create_task(db)
        storage = MemoryStorage()
        source_key = f"kiri/{task.scan_session_id}/source.glb"
        storage.put_bytes(source_key, b"glTF" + b"\x00" * 16, "model/gltf-binary")
        task.source_glb_path = source_key
        task.status = KiriTaskStatus.CROP_BAKING
        task.scan_session.status = ScanStatus.CROP_BAKING
        db.commit()

        service = KiriPipelineService(
            db,
            api=FakeKiriApi("successful", model_zip()),
            storage=storage,
        )

        service.publish_saved_project(task.scan_session_id)

        db.refresh(task)
        assert task.status == KiriTaskStatus.READY
        assert task.scan_session.status == ScanStatus.CROP_READY
        assert task.scan_session.model_asset is not None
        assert task.scan_session.model_asset.glb_path == source_key


def test_scan_session_ownership_is_required_for_kiri_routes() -> None:
    with database_session() as db:
        task = create_task(db)
        stranger = User(name="Stranger", email="stranger@example.com")
        db.add(stranger)
        db.commit()

        with pytest.raises(HTTPException) as exc:
            ScanSessionService(db).get_for_user(task.scan_session_id, stranger)

        assert exc.value.status_code == status.HTTP_404_NOT_FOUND


def test_start_processing_with_single_video_uploads_directly() -> None:
    with database_session() as db:
        user = User(name="Owner", email="owner@example.com")
        project = Project(user=user, name="Single scan")
        scan = ScanSession(
            user=user,
            project=project,
            status=ScanStatus.QUEUED,
            raw_video_path="videos/single.mp4",
        )
        db.add(scan)
        db.commit()
        db.refresh(scan)

        task = KiriScanTask(scan_session=scan, status=KiriTaskStatus.QUEUED)
        db.add(task)
        db.commit()

        storage = MemoryStorage()
        storage.put_bytes("videos/single.mp4", b"fake_mp4_video", "video/mp4")

        class RecordingKiriApi:
            def __init__(self) -> None:
                self.uploaded_bytes: bytes | None = None

            def upload_video(self, path: Path) -> str:
                self.uploaded_bytes = path.read_bytes()
                return "serialize-single"

        api = RecordingKiriApi()
        service = KiriPipelineService(db, api=api, storage=storage)
        service.start_processing(scan.id)

        db.refresh(task)
        db.refresh(scan)
        assert task.status == KiriTaskStatus.PROCESSING
        assert task.provider_serialize == "serialize-single"
        assert api.uploaded_bytes == b"fake_mp4_video"
        # Streaming via download_to, NEVER get_bytes for the video
        assert "videos/single.mp4" in storage.download_to_calls
        assert "videos/single.mp4" not in storage.get_bytes_calls
        # Video is deleted from storage once KIRI accepts
        assert "videos/single.mp4" in storage.deleted_keys
        assert not storage.exists("videos/single.mp4")
        assert scan.raw_video_path is None


def test_start_processing_cleans_temp_dir_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    with database_session() as db:
        user = User(name="Owner", email="owner@example.com")
        project = Project(user=user, name="Single scan")
        scan = ScanSession(
            user=user,
            project=project,
            status=ScanStatus.QUEUED,
            raw_video_path="videos/single.mp4",
        )
        db.add(scan)
        db.commit()

        task = KiriScanTask(scan_session=scan, status=KiriTaskStatus.QUEUED)
        db.add(task)
        db.commit()

        storage = MemoryStorage()
        storage.put_bytes("videos/single.mp4", b"fake_mp4_video", "video/mp4")

        created_dirs: list[str] = []
        real_mkdtemp = tempfile.mkdtemp

        def tracked_mkdtemp(*args: Any, **kwargs: Any) -> str:
            d = real_mkdtemp(*args, **kwargs)
            created_dirs.append(d)
            return d

        monkeypatch.setattr(tempfile, "mkdtemp", tracked_mkdtemp)

        class CrashingKiriApi:
            def upload_video(self, path: Path) -> str:
                raise RuntimeError("Network timeout during upload")

        service = KiriPipelineService(db, api=CrashingKiriApi(), storage=storage)
        service.start_processing(scan.id)

        db.refresh(task)
        assert task.status == KiriTaskStatus.FAILED
        assert len(created_dirs) == 1
        assert not Path(created_dirs[0]).exists()


def test_download_source_glb_cleans_temp_dir_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    with database_session() as db:
        task = create_task(db)
        storage = MemoryStorage()

        created_dirs: list[str] = []
        real_mkdtemp = tempfile.mkdtemp

        def tracked_mkdtemp(*args: Any, **kwargs: Any) -> str:
            d = real_mkdtemp(*args, **kwargs)
            created_dirs.append(d)
            return d

        monkeypatch.setattr(tempfile, "mkdtemp", tracked_mkdtemp)

        class CorruptZipKiriApi(FakeKiriApi):
            def download_model_zip_to(self, _model_url: str, target_path: Path) -> Path:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_bytes(b"not-a-zip-file")
                return target_path

        service = KiriPipelineService(
            db,
            api=CorruptZipKiriApi("successful", b"not-a-zip-file"),
            storage=storage,
        )

        refreshed = service.refresh(task)
        assert "invalid model ZIP" in (refreshed.error_message or "")
        assert len(created_dirs) == 1
        assert not Path(created_dirs[0]).exists()


class database_session:
    def __enter__(self) -> Session:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        return self.session

    def __exit__(self, *_args: Any) -> None:
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


class FakeControlPlaneClient:
    def __init__(self, status: str = "raw") -> None:
        self.status = status
        self.published_chunks: list[bytes] = []
        self.call_args: dict[str, Any] = {}

    def publish_glb(
        self,
        *,
        completion_token: str,
        expected_project_id: str,
        project_name: str,
        web_project_url: str,
        file_size_bytes: int,
        chunks: Any,
    ) -> ControlPlanePublishResult:
        self.published_chunks = list(chunks)
        self.call_args = {
            "completion_token": completion_token,
            "expected_project_id": expected_project_id,
            "project_name": project_name,
            "web_project_url": web_project_url,
            "file_size_bytes": file_size_bytes,
        }
        return ControlPlanePublishResult(
            project_id=expected_project_id,
            model_asset_id="asset-control-plane-1",
            status=self.status,
            web_project_url=web_project_url,
        )


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

    def download_model_zip_to(self, _model_url: str, target_path: Path) -> Path:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(self.zip_bytes)
        return target_path


class FailingKiriApi:
    def get_status(self, _serialize: str) -> str:
        raise KiriError("Kiri is temporarily unavailable.")


class FakeBlender:
    def require_available(self) -> str:
        return "blender"


class CaptureCropRunner:
    def __init__(self) -> None:
        self.command: list[str] = []

    def run(self, command: Any, **_kwargs: Any) -> CommandResult:
        self.command = command
        Path(command[-2]).write_bytes(b"glTF")
        return CommandResult(command=command, return_code=0, stdout="", stderr="")


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.get_bytes_calls: list[str] = []
        self.download_to_calls: list[str] = []
        self.deleted_keys: list[str] = []
        self.put_file_calls: list[str] = []

    def put_bytes(self, key: str, data: bytes, content_type: str) -> StoredObject:
        self.objects[key] = data
        return StoredObject(key, len(data), content_type, checksum_bytes(data))

    def put_file(self, key: str, file_path: Path, content_type: str) -> StoredObject:
        data = file_path.read_bytes()
        self.put_file_calls.append(key)
        return self.put_bytes(key, data, content_type)

    def get_bytes(self, key: str) -> bytes:
        self.get_bytes_calls.append(key)
        if key not in self.objects:
            raise KeyError(key)
        return self.objects[key]

    def download_to(self, key: str, target_path: Path) -> Path:
        self.download_to_calls.append(key)
        if key not in self.objects:
            raise KeyError(key)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(self.objects[key])
        return target_path

    def delete(self, key: str) -> None:
        self.deleted_keys.append(key)
        self.objects.pop(key, None)

    def head(self, key: str) -> dict[str, Any] | None:
        if key not in self.objects:
            return None
        return {"content_length": len(self.objects[key]), "content_type": "binary/octet-stream"}

    def iter_bytes(self, key: str, chunk_size: int = 1024 * 1024):
        if key not in self.objects:
            raise KeyError(key)
        yield self.objects[key]

    def exists(self, key: str) -> bool:
        return key in self.objects

    def create_upload_url(self, key: str, content_type: str = "video/mp4", expires_in: int = 900) -> str:
        return f"https://storage.example.com/{key}?upload=1"

    def create_signed_url(self, key: str, expires_in: int = 900) -> str | None:
        return f"https://storage.example.com/{key}?signed=1"

    def local_path(self, key: str) -> Path | None:
        return None