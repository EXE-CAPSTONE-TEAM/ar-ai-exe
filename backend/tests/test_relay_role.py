from __future__ import annotations

from typing import Any
from pathlib import Path

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.scan_deps import get_scan_actor
from app.core.config import Settings
from app.core.security import create_kiri_preview_ticket
from app.db.database import Base, get_db
from app.main import create_app
from app.models import KiriScanTask, KiriTaskStatus, ScanSession, ScanStatus, User
from app.services.storage import StoredObject, checksum_bytes, get_storage_service


class TrackingStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.get_bytes_calls: list[str] = []
        self.download_to_calls: list[str] = []
        self.deleted_keys: list[str] = []
        self.put_file_calls: list[str] = []
        self.custom_heads: dict[str, dict[str, Any]] = {}

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
        self.custom_heads.pop(key, None)

    def head(self, key: str) -> dict[str, Any] | None:
        if key in self.custom_heads:
            return self.custom_heads[key]
        if key not in self.objects:
            return None
        return {
            "content_length": len(self.objects[key]),
            "content_type": "video/mp4",
        }

    def exists(self, key: str) -> bool:
        return key in self.objects or key in self.custom_heads

    def create_upload_url(
        self, key: str, content_type: str = "video/mp4", expires_in: int = 900
    ) -> str:
        return f"https://storage.relay.test/{key}?upload=1&expires={expires_in}"

    def create_signed_url(self, key: str, expires_in: int = 900) -> str | None:
        return f"https://storage.relay.test/{key}?signed=1&expires={expires_in}"

    def iter_bytes(self, key: str, chunk_size: int = 1024 * 1024):
        if key not in self.objects:
            raise KeyError(key)
        yield self.objects[key]

    def local_path(self, key: str) -> Path | None:
        return None


def make_test_db() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def test_relay_role_mounts_only_scan_control_plane_and_health() -> None:
    settings = Settings(
        _env_file=None,
        app_role="relay",
        control_plane_service_token="should-be-cleared-in-relay",
    )
    assert settings.control_plane_service_token == ""

    app = create_app(settings)
    client = TestClient(app)

    # Mounted routes
    assert client.get("/health").status_code == 200
    # Scan sessions route responds with 401 Unauthorized (mounted, needs auth), not 404
    assert client.post("/api/scan-sessions").status_code == status.HTTP_401_UNAUTHORIZED
    # Control plane route responds with 422 Unprocessable (mounted, needs body), not 404
    assert client.post("/api/control-plane/scan/exchange").status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    # Excluded routes return 404 in relay mode
    assert client.get("/api/projects").status_code == status.HTTP_404_NOT_FOUND
    assert client.post("/api/auth/login").status_code == status.HTTP_404_NOT_FOUND
    assert client.get("/api/models").status_code == status.HTTP_404_NOT_FOUND
    assert client.get("/api/jobs").status_code == status.HTTP_404_NOT_FOUND
    assert client.post("/prepare").status_code == status.HTTP_404_NOT_FOUND
    assert client.post("/bake").status_code == status.HTTP_404_NOT_FOUND


def test_video_upload_url_returns_presigned_put_url() -> None:
    session = make_test_db()
    storage = TrackingStorage()
    settings = Settings(
        _env_file=None,
        app_role="relay",
        signed_url_ttl_seconds=900,
    )
    app = create_app(settings)
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_storage_service] = lambda: storage

    user = User(name="Mobile User", email="mobile@example.com")
    session.add(user)
    session.commit()

    scan = ScanSession(user=user, status=ScanStatus.CREATED)
    session.add(scan)
    session.commit()
    session.refresh(scan)

    app.dependency_overrides[get_scan_actor] = lambda: user

    client = TestClient(app)
    response = client.post(f"/api/scan-sessions/{scan.id}/video-upload-url")

    assert response.status_code == 200
    body = response.json()
    assert body["expiresIn"] == 900
    assert body["key"] == f"raw-scans/{scan.id}/scan.mp4"
    assert body["uploadUrl"].startswith(f"https://storage.relay.test/{body['key']}")


def test_video_uploaded_verifies_head_and_updates_status() -> None:
    session = make_test_db()
    storage = TrackingStorage()
    settings = Settings(_env_file=None, app_role="relay")
    app = create_app(settings)
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_storage_service] = lambda: storage

    user = User(name="Mobile User", email="mobile@example.com")
    session.add(user)
    session.commit()

    scan = ScanSession(user=user, status=ScanStatus.CREATED)
    session.add(scan)
    session.commit()
    session.refresh(scan)

    app.dependency_overrides[get_scan_actor] = lambda: user

    key = f"scan-sessions/{scan.id}/video_123.mp4"
    storage.put_bytes(key, b"fake_mp4_bytes", "video/mp4")

    client = TestClient(app)
    response = client.post(
        f"/api/scan-sessions/{scan.id}/video-uploaded",
        json={"key": key},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["scanSession"]["status"] == ScanStatus.UPLOADED
    assert body["readyForProcessing"] is True

    session.refresh(scan)
    assert scan.status == ScanStatus.UPLOADED
    assert scan.raw_video_path == key


def test_video_uploaded_rejects_missing_object_and_deletes() -> None:
    session = make_test_db()
    storage = TrackingStorage()
    settings = Settings(_env_file=None, app_role="relay")
    app = create_app(settings)
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_storage_service] = lambda: storage

    user = User(name="Mobile User", email="mobile@example.com")
    session.add(user)
    session.commit()

    scan = ScanSession(user=user, status=ScanStatus.CREATED)
    session.add(scan)
    session.commit()
    session.refresh(scan)

    app.dependency_overrides[get_scan_actor] = lambda: user

    key = f"scan-sessions/{scan.id}/video_missing.mp4"
    # Object is not in storage, so head will return None

    client = TestClient(app)
    response = client.post(
        f"/api/scan-sessions/{scan.id}/video-uploaded",
        json={"key": key},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "not found" in response.json()["error"]["message"]
    assert key in storage.deleted_keys


def test_video_uploaded_rejects_oversize_object_and_deletes() -> None:
    session = make_test_db()
    storage = TrackingStorage()
    settings = Settings(_env_file=None, app_role="relay", max_upload_size_mb=250)
    app = create_app(settings)
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_storage_service] = lambda: storage

    user = User(name="Mobile User", email="mobile@example.com")
    session.add(user)
    session.commit()

    scan = ScanSession(user=user, status=ScanStatus.CREATED)
    session.add(scan)
    session.commit()
    session.refresh(scan)

    app.dependency_overrides[get_scan_actor] = lambda: user

    key = f"scan-sessions/{scan.id}/video_oversize.mp4"
    storage.custom_heads[key] = {
        "content_length": 251 * 1024 * 1024,
        "content_type": "video/mp4",
    }

    client = TestClient(app)
    response = client.post(
        f"/api/scan-sessions/{scan.id}/video-uploaded",
        json={"key": key},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "between 1 byte and" in response.json()["error"]["message"]
    assert key in storage.deleted_keys


def test_video_uploaded_rejects_empty_object_and_deletes() -> None:
    session = make_test_db()
    storage = TrackingStorage()
    settings = Settings(_env_file=None, app_role="relay")
    app = create_app(settings)
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_storage_service] = lambda: storage

    user = User(name="Mobile User", email="mobile@example.com")
    session.add(user)
    session.commit()

    scan = ScanSession(user=user, status=ScanStatus.CREATED)
    session.add(scan)
    session.commit()
    session.refresh(scan)

    app.dependency_overrides[get_scan_actor] = lambda: user

    key = f"scan-sessions/{scan.id}/video_empty.mp4"
    storage.custom_heads[key] = {
        "content_length": 0,
        "content_type": "video/mp4",
    }

    client = TestClient(app)
    response = client.post(
        f"/api/scan-sessions/{scan.id}/video-uploaded",
        json={"key": key},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "between 1 byte and" in response.json()["error"]["message"]
    assert key in storage.deleted_keys


def test_kiri_preview_redirects_to_presigned_url_without_get_bytes() -> None:
    session = make_test_db()
    storage = TrackingStorage()
    settings = Settings(_env_file=None, app_role="relay", signed_url_ttl_seconds=900)
    app = create_app(settings)
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_storage_service] = lambda: storage

    user = User(name="Mobile User", email="mobile@example.com")
    session.add(user)
    session.commit()

    scan = ScanSession(user=user, status=ScanStatus.KIRI_READY)
    session.add(scan)
    session.commit()
    session.refresh(scan)

    glb_key = f"kiri/{scan.id}/source.glb"
    storage.put_bytes(glb_key, b"glTF" + b"\x00" * 16, "model/gltf-binary")

    task = KiriScanTask(
        scan_session=scan,
        provider_serialize="serial-1",
        provider_status="successful",
        status=KiriTaskStatus.READY_FOR_CROP,
        source_glb_path=glb_key,
    )
    session.add(task)
    session.commit()

    ticket = create_kiri_preview_ticket(scan.id)

    client = TestClient(app)
    response = client.get(
        f"/api/scan-sessions/{scan.id}/kiri/preview?ticket={ticket}",
        follow_redirects=False,
    )

    assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert response.headers["Location"].startswith(f"https://storage.relay.test/{glb_key}")
    # Verify get_bytes was NEVER called (no bytes served through API memory)
    assert glb_key not in storage.get_bytes_calls
