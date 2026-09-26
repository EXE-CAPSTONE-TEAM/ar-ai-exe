from __future__ import annotations

import asyncio
import json
from pathlib import Path
import struct
from types import SimpleNamespace
from typing import Any
import uuid

from fastapi import HTTPException
import httpx
from pydantic import ValidationError
import pytest

from app.api import worker
from app.core.config import Settings
from app.schemas.worker import PrepareWorkerRequest
from app.services.command_runner import CommandResult
from app.services.control_plane_prepare import ControlPlanePrepareService


# provenance: Khronos glTF 2.0 specification binary header magic 0x46546C67
def valid_glb(size: int = 12) -> bytes:
    header = struct.pack("<4sII", b"glTF", 2, size)
    if size > 12:
        return header + b"\x00" * (size - 12)
    return header


def prepare_request_payload(
    *,
    project_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    source_bytes: bytes | None = None,
) -> dict[str, Any]:
    proj_id = project_id or uuid.uuid4()
    jb_id = job_id or uuid.uuid4()
    source_data = source_bytes if source_bytes is not None else valid_glb()
    claim_id = uuid.uuid4()

    return {
        "job_id": str(jb_id),
        "project_id": str(proj_id),
        "crop_box": {
            "center": {"x": 0.1, "y": -0.1, "z": 0.0},
            "size": {"x": 0.8, "y": 0.9, "z": 0.7},
            "rotation": {"x": 5.0, "y": 0.0, "z": 0.0},
            "coordinateSpace": "normalized",
        },
        "source_model": {
            "asset_id": str(uuid.uuid4()),
            "download_url": "https://storage.test/raw_model.glb?sig=valid",
            "file_size_bytes": len(source_data),
            "mime_type": "model/gltf-binary",
        },
        "outputs": [
            {
                "format": "glb",
                "file_path": f"staging/{proj_id}/{jb_id}/{claim_id}/prepared.glb",
                "upload_url": "https://storage.test/upload_prepared.glb?sig=valid",
                "content_type": "model/gltf-binary",
            }
        ],
    }


class FakeBlender:
    def require_available(self) -> str:
        return "blender"


class FakeRunner:
    def __init__(self, report_payload: dict[str, Any] | None = None) -> None:
        self.report_payload = report_payload or {
            "editorReady": True,
            "editorReadyScore": 95,
            "meshObjectCount": 1,
            "boundingBox": {
                "before": {"maxDimension": 5.0},
                "after": {"maxDimension": 2.4},
            },
            "normalizedScale": 0.48,
            "triangleCountBefore": 10000,
            "triangleCountAfter": 7500,
            "cleanupWarnings": [],
        }
        self.commands: list[list[str]] = []
        self.cropped_bytes = valid_glb(24)
        self.prepared_bytes = valid_glb(36)

    def run(
        self,
        command: list[str],
        log_path: Path | None = None,
        cwd: Path | None = None,
        timeout: int | None = None,
        env: dict[str, str] | None = None,
    ) -> CommandResult:
        self.commands.append(command)
        command_str = " ".join(command)
        if "crop_glb.py" in command_str:
            output_glb = Path(command[-2])
            output_glb.parent.mkdir(parents=True, exist_ok=True)
            output_glb.write_bytes(self.cropped_bytes)
        elif "editor_ready_cleanup.py" in command_str:
            output_dir = Path(command[-4])
            report_path = Path(command[-3])
            output_dir.mkdir(parents=True, exist_ok=True)
            report_path.parent.mkdir(parents=True, exist_ok=True)
            (output_dir / "shoe_preview.glb").write_bytes(self.prepared_bytes)
            (output_dir / "shoe.obj").write_text("o shoe\n", encoding="utf-8")
            report_path.write_text(json.dumps(self.report_payload), encoding="utf-8")
        return CommandResult(command=command, return_code=0, stdout="", stderr="")


def test_prepare_schema_validates_and_rejects_invalid_inputs() -> None:
    payload = prepare_request_payload()
    model = PrepareWorkerRequest.model_validate(payload)
    assert model.outputs[0].format == "glb"
    assert model.crop_box.size.x == 0.8

    # Rejects path injection outside project/job
    bad_payload = prepare_request_payload()
    bad_payload["outputs"][0]["file_path"] = "exports/other-project/stolen.glb"
    with pytest.raises(ValidationError, match="canonical job path"):
        PrepareWorkerRequest.model_validate(bad_payload)

    # Rejects path traversal
    bad_traversal = prepare_request_payload()
    bad_traversal["outputs"][0]["file_path"] = f"staging/{model.project_id}/{model.job_id}/../../stolen.glb"
    with pytest.raises(ValidationError, match="canonical job path"):
        PrepareWorkerRequest.model_validate(bad_traversal)

    # Rejects non-glb format
    bad_fmt = prepare_request_payload()
    bad_fmt["outputs"][0]["format"] = "obj"
    with pytest.raises(ValidationError, match="glb"):
        PrepareWorkerRequest.model_validate(bad_fmt)

    # Rejects non-gltf-binary content type
    bad_ct = prepare_request_payload()
    bad_ct["outputs"][0]["content_type"] = "application/zip"
    with pytest.raises(ValidationError, match="model/gltf-binary"):
        PrepareWorkerRequest.model_validate(bad_ct)


def test_prepare_rejects_non_allowlisted_origins() -> None:
    payload = prepare_request_payload()
    request_model = PrepareWorkerRequest.model_validate(payload)

    # Rejects origin not in allowlist
    settings = Settings(
        environment="test",
        worker_allowed_storage_origins=["https://other-storage.test"],
    )
    service = ControlPlanePrepareService(settings=settings)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(service.execute(request_model))
    assert exc_info.value.status_code == 422
    assert "origin is not allowed" in exc_info.value.detail

    # Rejects when allowlist is unconfigured
    empty_settings = Settings(
        environment="test",
        worker_allowed_storage_origins=[],
    )
    service_unconfigured = ControlPlanePrepareService(settings=empty_settings)
    with pytest.raises(HTTPException) as unconf_info:
        asyncio.run(service_unconfigured.execute(request_model))
    assert unconf_info.value.status_code == 503
    assert "not configured" in unconf_info.value.detail


def test_prepare_rejects_oversize_sources() -> None:
    payload = prepare_request_payload()
    # Declared size exceeds worker_max_source_size_mb
    payload["source_model"]["file_size_bytes"] = 10 * 1024 * 1024
    request_model = PrepareWorkerRequest.model_validate(payload)

    settings = Settings(
        environment="test",
        worker_allowed_storage_origins=["https://storage.test"],
        worker_max_source_size_mb=1,
    )
    service = ControlPlanePrepareService(settings=settings)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(service.execute(request_model))
    assert exc_info.value.status_code == 422
    assert "exceeds the worker size limit" in exc_info.value.detail


def test_prepare_verifies_source_glb_magic() -> None:
    bad_magic = b"NOT_A_GLB_DATA"
    payload = prepare_request_payload(source_bytes=bad_magic)
    request_model = PrepareWorkerRequest.model_validate(payload)

    async def transport_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=bad_magic)

    transport = httpx.MockTransport(transport_handler)
    settings = Settings(
        environment="test",
        worker_allowed_storage_origins=["https://storage.test"],
    )
    service = ControlPlanePrepareService(
        settings=settings,
        client_factory=lambda: httpx.AsyncClient(transport=transport, follow_redirects=False),
        blender=FakeBlender(),
        runner=FakeRunner(),
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(service.execute(request_model))
    assert exc_info.value.status_code == 422
    assert "GLB file header is invalid" in exc_info.value.detail


def test_prepare_verifies_output_glb_magic() -> None:
    source = valid_glb(16)
    payload = prepare_request_payload(source_bytes=source)
    request_model = PrepareWorkerRequest.model_validate(payload)

    async def transport_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=source)

    transport = httpx.MockTransport(transport_handler)
    settings = Settings(
        environment="test",
        worker_allowed_storage_origins=["https://storage.test"],
    )

    # Test bad magic from crop output
    runner_bad_crop = FakeRunner()
    runner_bad_crop.cropped_bytes = b"BAD_CROP_MAGIC_DATA"
    service_crop_err = ControlPlanePrepareService(
        settings=settings,
        client_factory=lambda: httpx.AsyncClient(transport=transport, follow_redirects=False),
        blender=FakeBlender(),
        runner=runner_bad_crop,
    )
    with pytest.raises(HTTPException) as crop_info:
        asyncio.run(service_crop_err.execute(request_model))
    assert crop_info.value.status_code == 500
    assert "GLB file header is invalid" in crop_info.value.detail

    # Test bad magic from mesh cleanup output
    runner_bad_cleanup = FakeRunner()
    runner_bad_cleanup.prepared_bytes = b"BAD_CLEANUP_MAGIC"
    service_cleanup_err = ControlPlanePrepareService(
        settings=settings,
        client_factory=lambda: httpx.AsyncClient(transport=transport, follow_redirects=False),
        blender=FakeBlender(),
        runner=runner_bad_cleanup,
    )
    with pytest.raises(HTTPException) as cleanup_info:
        asyncio.run(service_cleanup_err.execute(request_model))
    assert cleanup_info.value.status_code == 500
    assert "GLB file header is invalid" in cleanup_info.value.detail


def test_prepare_runs_crop_then_cleanup_with_stubbed_runner_and_uploads() -> None:
    source_data = valid_glb(20)
    payload = prepare_request_payload(source_bytes=source_data)
    request_model = PrepareWorkerRequest.model_validate(payload)

    uploaded: dict[str, tuple[str, bytes]] = {}

    async def transport_handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/raw_model.glb":
            return httpx.Response(200, content=source_data)
        if request.method == "PUT" and request.url.path == "/upload_prepared.glb":
            uploaded[request.url.path] = (
                request.headers["content-type"],
                await request.aread(),
            )
            return httpx.Response(200)
        return httpx.Response(404)

    transport = httpx.MockTransport(transport_handler)
    fake_runner = FakeRunner()

    settings = Settings(
        environment="test",
        worker_allowed_storage_origins=["https://storage.test"],
        worker_max_source_size_mb=10,
    )
    service = ControlPlanePrepareService(
        settings=settings,
        client_factory=lambda: httpx.AsyncClient(transport=transport, follow_redirects=False),
        blender=FakeBlender(),
        runner=fake_runner,
    )

    response = asyncio.run(service.execute(request_model))

    # Output verification
    assert len(response.outputs) == 1
    output = response.outputs[0]
    assert output.format == "glb"
    assert output.file_path == payload["outputs"][0]["file_path"]
    assert output.file_size_bytes == len(fake_runner.prepared_bytes)

    # Uploaded bytes verification
    assert "/upload_prepared.glb" in uploaded
    uploaded_content_type, uploaded_bytes = uploaded["/upload_prepared.glb"]
    assert uploaded_content_type == "model/gltf-binary"
    assert uploaded_bytes == fake_runner.prepared_bytes

    # Cleanup report verification
    assert response.cleanup_report["editorReady"] is True
    assert response.cleanup_report["editorReadyScore"] == 95
    assert response.cleanup_report["meshObjectCount"] == 1

    # Verify command sequence: crop first, cleanup second
    assert len(fake_runner.commands) == 2
    crop_cmd, cleanup_cmd = fake_runner.commands
    assert any("crop_glb.py" in arg for arg in crop_cmd)
    assert any("editor_ready_cleanup.py" in arg for arg in cleanup_cmd)


def test_prepare_endpoint_authentication_and_concurrency(monkeypatch) -> None:
    # 503 when token unconfigured
    monkeypatch.setattr(
        worker,
        "get_settings",
        lambda: SimpleNamespace(control_plane_service_token=""),
    )
    with pytest.raises(HTTPException) as unconf:
        worker.require_control_plane_token("any-token")
    assert unconf.value.status_code == 503

    # 401 when token invalid
    monkeypatch.setattr(
        worker,
        "get_settings",
        lambda: SimpleNamespace(control_plane_service_token="valid-secret-token-32-bytes"),
    )
    with pytest.raises(HTTPException) as invalid:
        worker.require_control_plane_token("wrong-token")
    assert invalid.value.status_code == 401

    # Succeeds with matching token
    assert worker.require_control_plane_token("valid-secret-token-32-bytes") is None

    # Test concurrency limit when semaphore is exhausted
    payload = prepare_request_payload()
    request_model = PrepareWorkerRequest.model_validate(payload)

    worker._bake_slots.acquire(blocking=False)
    try:
        with pytest.raises(HTTPException) as busy:
            asyncio.run(worker.prepare(request_model, None))
        assert busy.value.status_code == 503
        assert busy.value.detail == "Prepare worker is at capacity."
        assert busy.value.headers == {"Retry-After": "10"}
    finally:
        worker._bake_slots.release()
