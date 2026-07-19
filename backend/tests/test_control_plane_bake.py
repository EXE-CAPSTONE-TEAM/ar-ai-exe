import asyncio
import struct
import uuid
import zipfile
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api import worker
from app.core.capability_urls import canonical_origin
from app.core.config import Settings
from app.schemas.worker import BakeWorkerRequest
from app.services.control_plane_bake import ControlPlaneBakeService
from app.services.decal_baker import DecalBakeService


def valid_glb() -> bytes:
    return struct.pack("<4sII", b"glTF", 2, 12)


def request_payload(*, include_asset: bool = False) -> dict:
    project_id = uuid.uuid4()
    job_id = uuid.uuid4()
    source_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    design_config = {
        "modelAssetId": str(source_id),
        "stickers": ([{"assetId": str(asset_id)}] if include_asset else []),
        "texts": [],
    }
    return {
        "job_id": str(job_id),
        "project_id": str(project_id),
        "design_config": design_config,
        "formats": ["glb", "obj"],
        "source_model": {
            "asset_id": str(source_id),
            "download_url": "https://storage.test/source.glb?signature=secret",
            "file_size_bytes": len(valid_glb()),
            "mime_type": "model/gltf-binary",
        },
        "asset_downloads": (
            [
                {
                    "asset_id": str(asset_id),
                    "download_url": "https://storage.test/decal.png?signature=secret",
                    "file_size_bytes": 8,
                    "mime_type": "image/png",
                }
            ]
            if include_asset
            else []
        ),
        "outputs": [
            {
                "format": "glb",
                "file_path": (f"exports/{project_id}/{job_id}/final_shoe.glb"),
                "upload_url": "https://storage.test/out.glb?signature=secret",
                "content_type": "model/gltf-binary",
            },
            {
                "format": "obj",
                "file_path": (f"exports/{project_id}/{job_id}/final_shoe.obj.zip"),
                "upload_url": "https://storage.test/out.obj.zip?signature=secret",
                "content_type": "application/zip",
            },
        ],
    }


def test_worker_schema_rejects_output_path_injection():
    payload = request_payload()
    payload["outputs"][0]["file_path"] = "exports/another-project/stolen.glb"

    with pytest.raises(ValidationError, match="canonical job path"):
        BakeWorkerRequest.model_validate(payload)


def test_worker_schema_requires_exact_text_render_capabilities():
    payload = request_payload()
    payload["design_config"]["texts"] = [
        {
            "value": "KUS",
            "renderAssetId": str(uuid.uuid4()),
        }
    ]

    with pytest.raises(ValidationError, match="exactly match"):
        BakeWorkerRequest.model_validate(payload)


@pytest.mark.parametrize(
    "url",
    [
        "https://user:password@storage.test/object",
        "https://storage.test/object#fragment",
        "https://storage.test/",
        "file:///tmp/object",
        "https://storage.test\\@attacker.test/object",
    ],
)
def test_canonical_origin_rejects_ambiguous_capability_urls(url):
    with pytest.raises(ValueError):
        canonical_origin(url, origin_only=False, require_https=False)


def test_canonical_origin_requires_https_for_production():
    with pytest.raises(ValueError, match="HTTPS"):
        canonical_origin(
            "http://storage.test/object",
            origin_only=False,
            require_https=True,
        )


def test_worker_authentication_fails_closed(monkeypatch):
    monkeypatch.setattr(
        worker,
        "get_settings",
        lambda: SimpleNamespace(control_plane_service_token=""),
    )
    with pytest.raises(HTTPException) as unconfigured:
        worker.require_control_plane_token("anything")
    assert unconfigured.value.status_code == 503

    monkeypatch.setattr(
        worker,
        "get_settings",
        lambda: SimpleNamespace(control_plane_service_token="s" * 32),
    )
    with pytest.raises(HTTPException) as invalid:
        worker.require_control_plane_token("wrong")
    assert invalid.value.status_code == 401

    assert worker.require_control_plane_token("s" * 32) is None


def test_service_streams_capabilities_bakes_and_uploads_exact_outputs():
    payload = request_payload(include_asset=True)
    request_model = BakeWorkerRequest.model_validate(payload)
    png = b"\x89PNG\r\n\x1a\n"
    uploaded: dict[str, tuple[str, bytes]] = {}

    async def transport_handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/source.glb":
            return httpx.Response(200, content=valid_glb())
        if request.method == "GET" and request.url.path == "/decal.png":
            return httpx.Response(200, content=png)
        if request.method == "PUT":
            uploaded[request.url.path] = (
                request.headers["content-type"],
                await request.aread(),
            )
            return httpx.Response(200)
        return httpx.Response(404)

    transport = httpx.MockTransport(transport_handler)

    class FakeBaker:
        def __init__(self, *, asset_resolver):
            self.asset_resolver = asset_resolver

        def bake(
            self,
            _source_path,
            output_dir,
            design_config,
            *,
            force_material_bake,
        ):
            assert force_material_bake is True
            asset_bytes, mime_type = self.asset_resolver(design_config["stickers"][0]["assetId"])
            assert asset_bytes == png
            assert mime_type == "image/png"

            output_dir.joinpath("final_shoe.glb").write_bytes(valid_glb())
            output_dir.joinpath("final_shoe.obj").write_text(
                "mtllib final_shoe.mtl\n",
                encoding="utf-8",
            )
            output_dir.joinpath("final_shoe.mtl").write_text(
                "newmtl shoe\nmap_Kd stickers/decal.png\n",
                encoding="utf-8",
            )
            stickers_dir = output_dir / "stickers"
            stickers_dir.mkdir()
            stickers_dir.joinpath("decal.png").write_bytes(asset_bytes)
            return True

    settings = Settings(
        environment="test",
        worker_allowed_storage_origins=["https://storage.test"],
        worker_max_source_size_mb=1,
        worker_max_asset_size_mb=1,
        worker_max_output_size_mb=10,
    )
    service = ControlPlaneBakeService(
        settings=settings,
        client_factory=lambda: httpx.AsyncClient(
            transport=transport,
            follow_redirects=False,
        ),
        baker_factory=FakeBaker,
    )

    response = asyncio.run(service.execute(request_model))

    assert [item.format for item in response.exports] == ["glb", "obj"]
    assert uploaded["/out.glb"] == ("model/gltf-binary", valid_glb())
    obj_content_type, obj_archive = uploaded["/out.obj.zip"]
    assert obj_content_type == "application/zip"

    archive_path = settings.resolved_storage_root.parent / "_unused-worker-test.zip"
    try:
        archive_path.write_bytes(obj_archive)
        with zipfile.ZipFile(archive_path) as archive:
            assert set(archive.namelist()) == {
                "final_shoe.obj",
                "final_shoe.mtl",
                "stickers/decal.png",
            }
    finally:
        archive_path.unlink(missing_ok=True)


def test_service_rejects_cross_origin_before_network():
    request_model = BakeWorkerRequest.model_validate(request_payload())
    settings = Settings(
        environment="test",
        worker_allowed_storage_origins=["https://other-storage.test"],
    )
    service = ControlPlaneBakeService(settings=settings)

    with pytest.raises(HTTPException) as rejected:
        asyncio.run(service.execute(request_model))

    assert rejected.value.status_code == 422


def test_force_material_bake_runs_without_decals(tmp_path):
    source = tmp_path / "source.glb"
    source.write_bytes(valid_glb())
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    class FakeBlender:
        @staticmethod
        def require_available():
            return "blender"

    class FakeRunner:
        @staticmethod
        def run(_command, *, log_path, cwd, timeout):
            assert log_path.parent.name == "_work"
            assert cwd == output_dir
            assert timeout == 10
            output_dir.joinpath("final_shoe.glb").write_bytes(valid_glb())
            output_dir.joinpath("final_shoe.obj").write_text("o shoe\n")
            output_dir.joinpath("final_shoe.mtl").write_text("newmtl shoe\n")
            return SimpleNamespace(ok=True, stderr="", stdout="")

    service = object.__new__(DecalBakeService)
    service.settings = SimpleNamespace(reconstruction_command_timeout_seconds=10)
    service.blender = FakeBlender()
    service.runner = FakeRunner()
    service.asset_resolver = None

    assert (
        service.bake(
            source,
            output_dir,
            {"stickers": [], "texts": [], "baseColor": "#112233"},
            force_material_bake=True,
        )
        is True
    )
