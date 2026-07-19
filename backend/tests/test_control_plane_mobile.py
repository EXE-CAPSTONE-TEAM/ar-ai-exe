from __future__ import annotations

import json
import struct
import uuid
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.api.control_plane_mobile as control_plane_api
import app.core.control_plane_scan_tokens as scan_tokens
from app.api.control_plane_mobile import (
    get_control_plane_mobile_client,
    router,
)
from app.api.scan_sessions import scan_response
from app.core.config import Settings
from app.core.control_plane_scan_tokens import decode_control_plane_scan_token
from app.core.scan_identity import ControlPlaneScanPrincipal
from app.db.database import Base
from app.models import ScanSession
from app.schemas.control_plane_mobile import ControlPlaneGrantClaimResponse
from app.services.control_plane_mobile import (
    ControlPlaneConfigurationError,
    ControlPlaneContractError,
    ControlPlaneGrantRejected,
    ControlPlaneMobileClient,
    _validated_glb_stream,
)
from app.services.scan_sessions import ScanSessionService
from app.services.storage import StoredObject, checksum_bytes


PROJECT_ID = uuid.UUID("d77a39f7-2fef-478e-adc9-04e05507aa81")
USER_ID = uuid.UUID("c908600f-d74e-42eb-af8b-36f91d8e59ae")
ASSET_ID = uuid.UUID("92a9fa02-9f54-4116-aebd-510472d552e3")
COMPUTE_GRANT = "g" * 43
COMPLETION_TOKEN = "c" * 43


def control_plane_settings(**overrides) -> Settings:
    values = {
        "environment": "test",
        "control_plane_api_base_url": "https://control.test",
        "control_plane_mobile_service_token": "mobile-service-secret",
        "control_plane_allowed_storage_origins": ["https://storage.test"],
        "control_plane_mobile_request_timeout_seconds": 30,
        "control_plane_max_output_size_mb": 5,
        "jwt_secret_key": "test-jwt-secret-that-is-long-enough",
        "control_plane_scan_token_minutes": 15,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def valid_glb(payload: bytes = b"model") -> bytes:
    size = 12 + len(payload)
    return struct.pack("<4sII", b"glTF", 2, size) + payload


def test_client_claims_grant_and_publishes_exact_glb_without_storage_credentials() -> None:
    glb = valid_glb()
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        if request.url.path.endswith("/compute-grants/claim"):
            assert request.headers["X-Service-Token"] == "mobile-service-secret"
            assert json.loads(request.content) == {"compute_grant": COMPUTE_GRANT}
            return httpx.Response(
                200,
                json={
                    "user_id": str(USER_ID),
                    "project_id": str(PROJECT_ID),
                    "project_name": "Canonical scan",
                    "completion_token": COMPLETION_TOKEN,
                    "web_project_url": f"https://kusshoes.vn/projects/{PROJECT_ID}",
                },
            )
        if request.url.path.endswith("/scans/output-upload"):
            assert request.headers["X-Service-Token"] == "mobile-service-secret"
            return httpx.Response(
                200,
                json={
                    "project_id": str(PROJECT_ID),
                    "asset_id": str(ASSET_ID),
                    "file_path": f"source_models/{PROJECT_ID}/{ASSET_ID}.glb",
                    "upload_url": "https://storage.test/signed/model.glb?signature=secret",
                    "expires_in": 900,
                    "already_completed": False,
                },
            )
        if request.url.path == "/signed/model.glb":
            assert "x-service-token" not in request.headers
            assert request.headers["Content-Type"] == "model/gltf-binary"
            assert request.headers["Content-Length"] == str(len(glb))
            assert request.read() == glb
            return httpx.Response(200)
        if request.url.path.endswith("/scans/output-confirm"):
            assert request.headers["X-Service-Token"] == "mobile-service-secret"
            assert json.loads(request.content) == {
                "completion_token": COMPLETION_TOKEN,
                "asset_id": str(ASSET_ID),
                "file_size_bytes": len(glb),
                "project_name": "Canonical scan",
            }
            return httpx.Response(
                200,
                json={
                    "project_id": str(PROJECT_ID),
                    "model_asset_id": str(ASSET_ID),
                    "status": "ready",
                    "web_project_url": f"https://kusshoes.vn/projects/{PROJECT_ID}",
                },
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    transport = httpx.MockTransport(handler)
    client = ControlPlaneMobileClient(
        settings=control_plane_settings(),
        client_factory=lambda: httpx.Client(transport=transport),
    )

    claim = client.claim_compute_grant(COMPUTE_GRANT)
    result = client.publish_glb(
        completion_token=claim.completion_token,
        expected_project_id=str(PROJECT_ID),
        project_name=claim.project_name,
        web_project_url=claim.web_project_url,
        file_size_bytes=len(glb),
        chunks=[glb[:7], glb[7:]],
    )

    assert claim.user_id == USER_ID
    assert result.model_asset_id == str(ASSET_ID)
    assert result.status == "ready"
    assert seen_paths == [
        "/api/v1/internal/mobile/compute-grants/claim",
        "/api/v1/internal/mobile/scans/output-upload",
        "/signed/model.glb",
        "/api/v1/internal/mobile/scans/output-confirm",
    ]


def test_client_rejects_non_allowlisted_presigned_upload_origin() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/scans/output-upload")
        return httpx.Response(
            200,
            json={
                "project_id": str(PROJECT_ID),
                "asset_id": str(ASSET_ID),
                "file_path": "source_models/model.glb",
                "upload_url": "https://attacker.test/model.glb",
                "expires_in": 900,
                "already_completed": False,
            },
        )

    glb = valid_glb()
    client = ControlPlaneMobileClient(
        settings=control_plane_settings(),
        client_factory=lambda: httpx.Client(
            transport=httpx.MockTransport(handler)
        ),
    )

    with pytest.raises(ControlPlaneConfigurationError, match="allowlisted"):
        client.publish_glb(
            completion_token=COMPLETION_TOKEN,
            expected_project_id=str(PROJECT_ID),
            project_name="Canonical scan",
            web_project_url=f"https://kusshoes.vn/projects/{PROJECT_ID}",
            file_size_bytes=len(glb),
            chunks=[glb],
        )


def test_client_distinguishes_invalid_grant_from_service_auth_failure() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={
                "code": "MOBILE_SCAN_GRANT_INVALID",
                "message": "expired",
            },
        )

    client = ControlPlaneMobileClient(
        settings=control_plane_settings(),
        client_factory=lambda: httpx.Client(
            transport=httpx.MockTransport(handler)
        ),
    )

    with pytest.raises(ControlPlaneGrantRejected):
        client.claim_compute_grant(COMPUTE_GRANT)


def test_glb_stream_requires_exact_v2_header_and_declared_size() -> None:
    with pytest.raises(ControlPlaneContractError, match="header"):
        list(_validated_glb_stream([b"not-a-valid-glb"], 15))


def test_exchange_issues_project_scoped_token_without_returning_completion_capability(
    monkeypatch,
) -> None:
    settings = control_plane_settings()
    monkeypatch.setattr(scan_tokens, "get_settings", lambda: settings)
    monkeypatch.setattr(control_plane_api, "get_settings", lambda: settings)
    claim = ControlPlaneGrantClaimResponse(
        user_id=USER_ID,
        project_id=PROJECT_ID,
        project_name="Canonical scan",
        completion_token=COMPLETION_TOKEN,
        web_project_url=f"https://kusshoes.vn/projects/{PROJECT_ID}",
    )
    fake_client = FakeClaimClient(claim)
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api")
    test_app.dependency_overrides[get_control_plane_mobile_client] = (
        lambda: fake_client
    )

    with TestClient(test_app) as client:
        response = client.post(
            "/api/control-plane/scan/exchange",
            json={"computeGrant": COMPUTE_GRANT},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["projectId"] == str(PROJECT_ID)
    assert body["expiresIn"] == 900
    assert "completionToken" not in body
    principal = decode_control_plane_scan_token(body["accessToken"])
    assert principal.project_id == str(PROJECT_ID)
    assert principal.user_id == str(USER_ID)
    assert principal.completion_token == COMPLETION_TOKEN


def test_canonical_scan_creation_is_idempotent_and_has_no_shadow_owner() -> None:
    storage = MemoryStorage()
    principal = canonical_principal()
    with database_session() as db:
        service = ScanSessionService(db, storage=storage)

        first = service.create_control_plane(principal)
        second = service.create_control_plane(principal)
        response = scan_response(first, None)

        assert first.id == second.id == f"scan_cp_{PROJECT_ID.hex}"
        assert db.scalar(select(func.count()).select_from(ScanSession)) == 1
        assert first.user_id is None
        assert first.project_id is None
        assert first.control_plane_project_id == str(PROJECT_ID)
        assert response.user_id == str(USER_ID)
        assert response.project_id == str(PROJECT_ID)
        assert not hasattr(response, "completion_token")

        with pytest.raises(HTTPException) as denied:
            service.get_for_actor(
                first.id,
                canonical_principal(project_id=uuid.uuid4()),
            )
        assert denied.value.status_code == 404

        with pytest.raises(HTTPException) as conflict:
            service.create_control_plane(
                canonical_principal(completion_token="x" * 43)
            )
        assert conflict.value.status_code == 409


def test_database_rejects_ownerless_scan_session() -> None:
    with database_session() as db:
        db.add(ScanSession())
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def canonical_principal(
    *,
    project_id: uuid.UUID = PROJECT_ID,
    completion_token: str = COMPLETION_TOKEN,
) -> ControlPlaneScanPrincipal:
    return ControlPlaneScanPrincipal(
        user_id=str(USER_ID),
        project_id=str(project_id),
        completion_token=completion_token,
        project_name="Canonical scan",
        web_project_url=f"https://kusshoes.vn/projects/{project_id}",
    )


@contextmanager
def database_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


class FakeClaimClient:
    def __init__(self, claim: ControlPlaneGrantClaimResponse) -> None:
        self.claim = claim

    def claim_compute_grant(
        self,
        compute_grant: str,
    ) -> ControlPlaneGrantClaimResponse:
        assert compute_grant == COMPUTE_GRANT
        return self.claim


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_bytes(self, key: str, data: bytes, content_type: str) -> StoredObject:
        self.objects[key] = data
        return StoredObject(key, len(data), content_type, checksum_bytes(data))

    def get_bytes(self, key: str) -> bytes:
        return self.objects[key]

    def iter_bytes(self, key: str, chunk_size: int = 1024 * 1024):
        data = self.objects[key]
        for offset in range(0, len(data), chunk_size):
            yield data[offset : offset + chunk_size]

    def exists(self, key: str) -> bool:
        return key in self.objects

    def create_signed_url(self, key: str, expires_in: int = 300) -> str | None:
        return None

    def local_path(self, key: str) -> Path | None:
        return None
