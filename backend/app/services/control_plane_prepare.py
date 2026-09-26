from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
import tempfile
from typing import Any

from fastapi import HTTPException, status
import httpx

from app.core.capability_urls import canonical_origin
from app.core.config import Settings, get_settings
from app.schemas.worker import (
    PrepareWorkerOutput,
    PrepareWorkerRequest,
    PrepareWorkerResponse,
)
from app.services.blender_service import BlenderService
from app.services.command_runner import CommandRunner
from app.services.control_plane_bake import (
    DOWNLOAD_CHUNK_BYTES,
    HARD_MAX_SOURCE_BYTES,
    MEBIBYTE,
    _iter_file,
    _require_regular_file,
    _verify_glb,
)
from app.services.crop_baker import CropBakeService
from app.services.mesh_cleanup import MeshCleanupReport, MeshCleanupService


def cleanup_report_to_dict(report: MeshCleanupReport | dict[str, Any]) -> dict[str, Any]:
    if isinstance(report, dict):
        return report
    return {
        "editor_ready": report.editor_ready,
        "editor_ready_score": report.editor_ready_score,
        "mesh_object_count": report.mesh_object_count,
        "bounding_box": report.bounding_box,
        "normalized_scale": report.normalized_scale,
        "triangle_count_before": report.triangle_count_before,
        "triangle_count_after": report.triangle_count_after,
        "cleanup_warnings": report.cleanup_warnings,
        **report.to_quality_fields(),
    }


def _require_bounded_output(path: Path, max_bytes: int) -> int:
    _require_regular_file(path)
    file_size = path.stat().st_size
    if file_size <= 0 or file_size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Prepare output exceeds the worker size limit.",
        )
    return file_size


class ControlPlanePrepareService:
    """Execute one capability-scoped prepare (crop + mesh cleanup) without database or storage credentials."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        client_factory: Callable[[], httpx.AsyncClient] | None = None,
        crop_baker_factory: Callable[..., CropBakeService] = CropBakeService,
        cleanup_service_factory: Callable[..., MeshCleanupService] = MeshCleanupService,
        runner: CommandRunner | None = None,
        blender: BlenderService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client_factory = client_factory or self._create_client
        self.crop_baker_factory = crop_baker_factory
        self.cleanup_service_factory = cleanup_service_factory
        self.runner = runner
        self.blender = blender

    @property
    def _source_limit(self) -> int:
        # provenance: spec §E.2, Parameter & Data Provenance table (500 MiB MAX_SOURCE_BYTES)
        configured = max(1, self.settings.worker_max_source_size_mb) * MEBIBYTE
        return min(configured, HARD_MAX_SOURCE_BYTES)

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

    def _validate_declared_limits(self, request: PrepareWorkerRequest) -> None:
        if request.source_model.file_size_bytes > self._source_limit:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Source model exceeds the worker size limit.",
            )

    def _validate_capability_origins(self, request: PrepareWorkerRequest) -> None:
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

    async def _upload(
        self,
        client: httpx.AsyncClient,
        *,
        url: str,
        source: Path,
        content_type: str,
        max_bytes: int,
    ) -> None:
        file_size = _require_bounded_output(source, max_bytes)
        response = await client.put(
            url,
            headers={
                "Content-Type": content_type,
                "Content-Length": str(file_size),
            },
            content=_iter_file(source),
        )
        response.raise_for_status()

    async def execute(self, request: PrepareWorkerRequest) -> PrepareWorkerResponse:
        self._validate_declared_limits(request)
        self._validate_capability_origins(request)

        try:
            with tempfile.TemporaryDirectory(prefix="kusshoes-prepare-") as raw_temp_dir:
                temp_dir = Path(raw_temp_dir)
                source_path = temp_dir / "source.glb"
                cropped_path = temp_dir / "cropped.glb"
                cleanup_dir = temp_dir / "cleanup_out"
                cleanup_dir.mkdir(parents=True, exist_ok=True)

                async with self.client_factory() as client:
                    await self._download(
                        client,
                        url=request.source_model.download_url,
                        destination=source_path,
                        expected_bytes=request.source_model.file_size_bytes,
                        max_bytes=self._source_limit,
                    )
                    _verify_glb(source_path, status.HTTP_422_UNPROCESSABLE_CONTENT)

                    crop_baker = self.crop_baker_factory(blender=self.blender, runner=self.runner)
                    await asyncio.to_thread(
                        crop_baker.bake,
                        source_path,
                        cropped_path,
                        request.crop_box,
                    )
                    _verify_glb(cropped_path, status.HTTP_500_INTERNAL_SERVER_ERROR)

                    cleanup_service = self.cleanup_service_factory(
                        blender=self.blender, runner=self.runner
                    )
                    cleanup_report = await asyncio.to_thread(
                        cleanup_service.cleanup,
                        cropped_path,
                        cleanup_dir,
                    )

                    prepared_glb = cleanup_dir / "shoe_preview.glb"
                    _verify_glb(prepared_glb, status.HTTP_500_INTERNAL_SERVER_ERROR)
                    file_size = _require_bounded_output(prepared_glb, self._source_limit)

                    outputs: list[PrepareWorkerOutput] = []
                    for capability in request.outputs:
                        await self._upload(
                            client,
                            url=capability.upload_url,
                            source=prepared_glb,
                            content_type=capability.content_type,
                            max_bytes=self._source_limit,
                        )
                        outputs.append(
                            PrepareWorkerOutput(
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
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Prepare worker failed: {exc}",
            ) from exc

        return PrepareWorkerResponse(
            outputs=outputs,
            cleanup_report=cleanup_report_to_dict(cleanup_report),
        )
