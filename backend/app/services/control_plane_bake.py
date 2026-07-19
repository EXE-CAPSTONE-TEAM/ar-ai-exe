from __future__ import annotations

import asyncio
import struct
import tempfile
import zipfile
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.capability_urls import canonical_origin
from app.core.config import Settings, get_settings
from app.schemas.worker import (
    BakeWorkerExport,
    BakeWorkerRequest,
    BakeWorkerResponse,
)
from app.services.decal_baker import DecalBakeService


MEBIBYTE = 1024 * 1024
HARD_MAX_SOURCE_BYTES = 500 * MEBIBYTE
HARD_MAX_ASSET_BYTES = 5 * MEBIBYTE
HARD_MAX_OUTPUT_BYTES = 2 * 1024 * MEBIBYTE
DOWNLOAD_CHUNK_BYTES = MEBIBYTE
IMAGE_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}
OBJ_BUNDLE_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".svg"}


class ControlPlaneBakeService:
    """Execute one capability-scoped bake without database or storage credentials."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        client_factory: Callable[[], httpx.AsyncClient] | None = None,
        baker_factory: Callable[..., DecalBakeService] = DecalBakeService,
    ) -> None:
        self.settings = settings or get_settings()
        self.client_factory = client_factory or self._create_client
        self.baker_factory = baker_factory

    async def execute(self, request: BakeWorkerRequest) -> BakeWorkerResponse:
        self._validate_declared_limits(request)
        self._validate_capability_origins(request)

        try:
            with tempfile.TemporaryDirectory(prefix="kusshoes-bake-") as raw_temp_dir:
                temp_dir = Path(raw_temp_dir)
                source_path = temp_dir / "source.glb"
                output_dir = temp_dir / "output"
                assets_dir = temp_dir / "assets"
                output_dir.mkdir()
                assets_dir.mkdir()

                async with self.client_factory() as client:
                    await self._download(
                        client,
                        url=request.source_model.download_url,
                        destination=source_path,
                        expected_bytes=request.source_model.file_size_bytes,
                        max_bytes=self._source_limit,
                    )
                    _verify_glb(source_path, status.HTTP_422_UNPROCESSABLE_CONTENT)

                    asset_files: dict[str, tuple[Path, str]] = {}
                    for capability in request.asset_downloads:
                        extension = IMAGE_EXTENSIONS[capability.mime_type]
                        destination = assets_dir / f"{capability.asset_id}{extension}"
                        await self._download(
                            client,
                            url=capability.download_url,
                            destination=destination,
                            expected_bytes=capability.file_size_bytes,
                            max_bytes=self._asset_limit,
                        )
                        _verify_image(destination, capability.mime_type)
                        asset_files[str(capability.asset_id)] = (
                            destination,
                            capability.mime_type,
                        )

                    await asyncio.to_thread(
                        self._run_bake,
                        source_path,
                        output_dir,
                        request.design_config,
                        asset_files,
                    )
                    output_files = self._prepare_output_files(
                        request,
                        output_dir,
                    )

                    exports: list[BakeWorkerExport] = []
                    for capability in request.outputs:
                        output_path = output_files[capability.format]
                        file_size = output_path.stat().st_size
                        await self._upload(
                            client,
                            url=capability.upload_url,
                            source=output_path,
                            content_type=capability.content_type,
                            max_bytes=self._output_limit,
                        )
                        exports.append(
                            BakeWorkerExport(
                                format=capability.format,
                                file_path=capability.file_path,
                                file_size_bytes=file_size,
                            )
                        )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Storage capability request failed.",
            ) from exc
        except OSError as exc:
            raise HTTPException(
                status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
                detail="Worker temporary storage is unavailable.",
            ) from exc

        return BakeWorkerResponse(exports=exports)

    @property
    def _source_limit(self) -> int:
        configured = max(1, self.settings.worker_max_source_size_mb) * MEBIBYTE
        return min(configured, HARD_MAX_SOURCE_BYTES)

    @property
    def _asset_limit(self) -> int:
        configured = max(1, self.settings.worker_max_asset_size_mb) * MEBIBYTE
        return min(configured, HARD_MAX_ASSET_BYTES)

    @property
    def _output_limit(self) -> int:
        configured = max(1, self.settings.worker_max_output_size_mb) * MEBIBYTE
        return min(configured, HARD_MAX_OUTPUT_BYTES)

    def _create_client(self) -> httpx.AsyncClient:
        timeout_seconds = max(1, self.settings.worker_request_timeout_seconds)
        return httpx.AsyncClient(
            timeout=httpx.Timeout(
                timeout_seconds,
                connect=min(timeout_seconds, 30),
            ),
            follow_redirects=False,
            trust_env=False,
            headers={"Accept-Encoding": "identity"},
        )

    def _validate_declared_limits(self, request: BakeWorkerRequest) -> None:
        if request.source_model.file_size_bytes > self._source_limit:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Source model exceeds the worker size limit.",
            )
        if any(item.file_size_bytes > self._asset_limit for item in request.asset_downloads):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Design asset exceeds the worker size limit.",
            )

    def _validate_capability_origins(self, request: BakeWorkerRequest) -> None:
        if not self.settings.worker_allowed_storage_origins:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Worker storage origin allowlist is not configured.",
            )

        production = self.settings.environment.lower() in {"prod", "production"}
        try:
            allowed_origins = {
                canonical_origin(origin, origin_only=True, require_https=production)
                for origin in self.settings.worker_allowed_storage_origins
            }
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Worker storage origin allowlist is invalid.",
            ) from exc

        capability_urls = [
            request.source_model.download_url,
            *(item.download_url for item in request.asset_downloads),
            *(item.upload_url for item in request.outputs),
        ]
        for capability_url in capability_urls:
            try:
                origin = canonical_origin(
                    capability_url,
                    origin_only=False,
                    require_https=production,
                )
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Storage capability URL is invalid.",
                ) from exc
            if origin not in allowed_origins:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Storage capability origin is not allowed.",
                )

    async def _download(
        self,
        client: httpx.AsyncClient,
        *,
        url: str,
        destination: Path,
        expected_bytes: int,
        max_bytes: int,
    ) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            content_encoding = response.headers.get("content-encoding", "").lower()
            if content_encoding not in {"", "identity"}:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Storage returned an encoded object.",
                )

            content_length = response.headers.get("content-length")
            if content_length:
                try:
                    declared_length = int(content_length)
                except ValueError as exc:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Storage returned an invalid object length.",
                    ) from exc
                if declared_length != expected_bytes or declared_length > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Storage object length does not match its capability.",
                    )

            total = 0
            with destination.open("wb") as stream:
                async for chunk in response.aiter_bytes(DOWNLOAD_CHUNK_BYTES):
                    total += len(chunk)
                    if total > max_bytes or total > expected_bytes:
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail="Storage object exceeded its declared size.",
                        )
                    stream.write(chunk)

        if total != expected_bytes:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Storage object size does not match its capability.",
            )

    def _run_bake(
        self,
        source_path: Path,
        output_dir: Path,
        design_config: dict[str, Any],
        asset_files: dict[str, tuple[Path, str]],
    ) -> None:
        def resolve_asset(asset_id: str) -> tuple[bytes, str]:
            resolved = asset_files.get(str(asset_id))
            if not resolved:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Design references an unavailable asset capability.",
                )
            path, mime_type = resolved
            return path.read_bytes(), mime_type

        baker = self.baker_factory(asset_resolver=resolve_asset)
        baked = baker.bake(
            source_path,
            output_dir,
            design_config,
            force_material_bake=True,
        )
        if not baked:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Bake worker produced no output.",
            )

    def _prepare_output_files(
        self,
        request: BakeWorkerRequest,
        output_dir: Path,
    ) -> dict[str, Path]:
        requested_formats = set(request.formats)
        result: dict[str, Path] = {}

        if "glb" in requested_formats:
            glb_path = output_dir / "final_shoe.glb"
            _verify_glb(glb_path, status.HTTP_500_INTERNAL_SERVER_ERROR)
            _require_bounded_file(glb_path, self._output_limit)
            result["glb"] = glb_path

        if "obj" in requested_formats:
            archive_path = output_dir / "final_shoe.obj.zip"
            self._build_obj_bundle(output_dir, archive_path)
            _require_bounded_file(archive_path, self._output_limit)
            result["obj"] = archive_path

        return result

    def _build_obj_bundle(self, output_dir: Path, archive_path: Path) -> None:
        required = [
            output_dir / "final_shoe.obj",
            output_dir / "final_shoe.mtl",
        ]
        for path in required:
            _require_regular_file(path)

        candidates = list(required)
        for path in output_dir.rglob("*"):
            if (
                path in candidates
                or path == archive_path
                or not path.is_file()
                or path.is_symlink()
                or "_work" in path.relative_to(output_dir).parts
                or path.suffix.lower() not in OBJ_BUNDLE_IMAGE_SUFFIXES
            ):
                continue
            candidates.append(path)

        uncompressed_size = sum(path.stat().st_size for path in candidates)
        if uncompressed_size <= 0 or uncompressed_size > self._output_limit:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="OBJ bundle exceeds the worker output limit.",
            )

        with zipfile.ZipFile(
            archive_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
        ) as archive:
            for path in candidates:
                archive.write(path, path.relative_to(output_dir).as_posix())

    async def _upload(
        self,
        client: httpx.AsyncClient,
        *,
        url: str,
        source: Path,
        content_type: str,
        max_bytes: int,
    ) -> None:
        file_size = _require_bounded_file(source, max_bytes)
        response = await client.put(
            url,
            headers={
                "Content-Type": content_type,
                "Content-Length": str(file_size),
            },
            content=_iter_file(source),
        )
        response.raise_for_status()


async def _iter_file(path: Path) -> AsyncIterator[bytes]:
    with path.open("rb") as stream:
        while chunk := stream.read(DOWNLOAD_CHUNK_BYTES):
            yield chunk


def _verify_glb(path: Path, status_code: int) -> None:
    _require_regular_file(path)
    file_size = path.stat().st_size
    if file_size < 12:
        raise HTTPException(status_code=status_code, detail="GLB file is truncated.")

    with path.open("rb") as stream:
        magic, version, declared_length = struct.unpack("<4sII", stream.read(12))
    if magic != b"glTF" or version != 2 or declared_length != file_size:
        raise HTTPException(status_code=status_code, detail="GLB file header is invalid.")


def _verify_image(path: Path, mime_type: str) -> None:
    _require_regular_file(path)
    with path.open("rb") as stream:
        header = stream.read(16)

    valid = {
        "image/png": header.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/jpeg": header.startswith(b"\xff\xd8\xff"),
        "image/webp": (
            len(header) >= 12 and header.startswith(b"RIFF") and header[8:12] == b"WEBP"
        ),
    }.get(mime_type, False)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Design asset content does not match its declared MIME type.",
        )


def _require_regular_file(path: Path) -> None:
    if not path.is_file() or path.is_symlink():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bake worker did not produce a required output file.",
        )


def _require_bounded_file(path: Path, max_bytes: int) -> int:
    _require_regular_file(path)
    file_size = path.stat().st_size
    if file_size <= 0 or file_size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bake output exceeds the worker size limit.",
        )
    return file_size
