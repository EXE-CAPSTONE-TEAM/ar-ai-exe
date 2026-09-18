"""End-to-End integration tests for compute worker and control plane mock storage."""

from __future__ import annotations

import asyncio
import os
import struct
import sys
import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

# Ensure repo root is in sys.path
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.config import Settings, get_settings
from app.schemas.worker import BakeWorkerRequest
from app.services.control_plane_bake import ControlPlaneBakeService
from app.services.decal_baker import DecalBakeService
from harness.doctor import find_blender_binary
from harness.fixtures.procedural_mesh import (
    SAMPLE_SVG_DATA_URI,
    build_design_payload,
    generate_curved_test_mesh,
    sample_sticker_config,
)
from tests.harness_control_plane.mock_storage import MockHermeticStorage


@pytest.fixture(scope="module")
def ensure_blender() -> Path:
    binary = find_blender_binary()
    if not binary:
        pytest.skip("Blender executable required for worker e2e test.")
    os.environ["BLENDER_BIN"] = str(binary)
    get_settings.cache_clear()
    return binary


def test_worker_e2e_real_bake_and_upload(ensure_blender: Path, tmp_path: Path) -> None:
    """Test full cycle: Worker downloads source GLB from mock storage, runs real Blender bake,

    and uploads the resulting GLB and OBJ artifacts back to mock presigned URLs.
    """
    storage = MockHermeticStorage(base_origin="https://storage.kusshoes.test")

    # 1. Prepare procedural source mesh
    source_glb = tmp_path / "source.glb"
    generate_curved_test_mesh(source_glb, ensure_blender)
    source_bytes = source_glb.read_bytes()

    source_download_url = storage.register_file(
        "models/source_shoe.glb",
        source_bytes,
        content_type="model/gltf-binary",
    )

    project_id = uuid.uuid4()
    job_id = uuid.uuid4()
    source_id = uuid.uuid4()

    sticker = sample_sticker_config(
        sticker_id="worker_sticker_01",
        image_url=SAMPLE_SVG_DATA_URI,
        position=[0.0, 0.0, 0.2],
        scale=0.2,
    )
    design = build_design_payload(stickers=[sticker])

    glb_upload_path = f"/exports/{project_id}/{job_id}/final_shoe.glb"
    obj_upload_path = f"/exports/{project_id}/{job_id}/final_shoe.obj.zip"

    request_payload = {
        "job_id": str(job_id),
        "project_id": str(project_id),
        "design_config": design,
        "formats": ["glb", "obj"],
        "source_model": {
            "asset_id": str(source_id),
            "download_url": source_download_url,
            "file_size_bytes": len(source_bytes),
            "mime_type": "model/gltf-binary",
        },
        "asset_downloads": [],
        "outputs": [
            {
                "format": "glb",
                "file_path": glb_upload_path.lstrip("/"),
                "upload_url": storage.get_upload_url(glb_upload_path),
                "content_type": "model/gltf-binary",
            },
            {
                "format": "obj",
                "file_path": obj_upload_path.lstrip("/"),
                "upload_url": storage.get_upload_url(obj_upload_path),
                "content_type": "application/zip",
            },
        ],
    }

    request_model = BakeWorkerRequest.model_validate(request_payload)

    settings = Settings(
        environment="test",
        worker_allowed_storage_origins=["https://storage.kusshoes.test"],
        worker_max_source_size_mb=10,
        worker_max_asset_size_mb=5,
        worker_max_output_size_mb=20,
    )

    # Instantiate real service with Mock storage client factory
    service = ControlPlaneBakeService(
        settings=settings,
        client_factory=storage.client_factory(),
        baker_factory=DecalBakeService,
    )

    # Execute worker bake
    response = asyncio.run(service.execute(request_model))

    # Assert response
    assert len(response.exports) == 2
    formats = {exp.format for exp in response.exports}
    assert formats == {"glb", "obj"}

    # Assert artifacts were uploaded to mock storage
    assert storage.has_uploaded(glb_upload_path)
    assert storage.has_uploaded(obj_upload_path)

    # Verify uploaded GLB header
    uploaded_glb = storage.get_uploaded_data(glb_upload_path)
    assert len(uploaded_glb) > 500
    magic, version, length = struct.unpack("<4sII", uploaded_glb[:12])
    assert magic == b"glTF"
    assert version == 2
    assert length == len(uploaded_glb)


def test_worker_rejects_untrusted_storage_origins(tmp_path: Path) -> None:
    """Security test: Worker must reject download or upload URLs from unauthorized origins."""
    settings = Settings(
        environment="test",
        worker_allowed_storage_origins=["https://trusted-storage.kusshoes.vn"],
    )
    service = ControlPlaneBakeService(settings=settings)

    project_id = uuid.uuid4()
    job_id = uuid.uuid4()
    evil_payload = {
        "job_id": str(job_id),
        "project_id": str(project_id),
        "design_config": {"stickers": [], "texts": []},
        "formats": ["glb"],
        "source_model": {
            "asset_id": str(uuid.uuid4()),
            "download_url": "https://evil-attacker.com/malicious.glb",
            "file_size_bytes": 1000,
            "mime_type": "model/gltf-binary",
        },
        "asset_downloads": [],
        "outputs": [
            {
                "format": "glb",
                "file_path": f"exports/{project_id}/{job_id}/final_shoe.glb",
                "upload_url": f"https://trusted-storage.kusshoes.vn/exports/{project_id}/{job_id}/final_shoe.glb",
                "content_type": "model/gltf-binary",
            }
        ],
    }
    request_model = BakeWorkerRequest.model_validate(evil_payload)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(service.execute(request_model))

    assert exc.value.status_code == 422
    assert "origin is not allowed" in exc.value.detail
