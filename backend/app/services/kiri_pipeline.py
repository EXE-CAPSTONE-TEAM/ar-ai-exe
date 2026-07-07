from __future__ import annotations

import io
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_kiri_preview_ticket
from app.models import (
    KiriScanTask,
    KiriTaskStatus,
    ModelAsset,
    ProjectSourceType,
    ProjectStatus,
    ScanSession,
    ScanStatus,
)
from app.schemas.scan import CropBox, KiriStatusResponse
from app.services.command_runner import CommandRunner
from app.services.crop_baker import CropBakeService
from app.services.file_helpers import write_json
from app.services.kiri_client import KiriApiClient, KiriError
from app.services.mesh_cleanup import MeshCleanupService
from app.services.model_assets import ModelAssetFiles, ModelAssetService
from app.services.scan_sessions import ScanSessionService
from app.services.storage import StorageService, get_storage_service


PROVIDER_ACTIVE_STATUSES = {"uploading", "queuing", "queued", "processing"}
TERMINAL_TASK_STATUSES = {KiriTaskStatus.READY, KiriTaskStatus.FAILED, KiriTaskStatus.EXPIRED}


class KiriPipelineService:
    def __init__(
        self,
        db: Session,
        *,
        api: KiriApiClient | None = None,
        storage: StorageService | None = None,
        runner: CommandRunner | None = None,
        crop_baker: CropBakeService | None = None,
        mesh_cleanup: MeshCleanupService | None = None,
    ) -> None:
        self.db = db
        self.settings = get_settings()
        self.api = api or KiriApiClient()
        self.storage = storage or get_storage_service()
        self.runner = runner or CommandRunner()
        self.crop_baker = crop_baker or CropBakeService()
        self.mesh_cleanup = mesh_cleanup or MeshCleanupService()
        self.asset_service = ModelAssetService(db, storage=self.storage)
        self.scan_service = ScanSessionService(db)

    def create_task(self, scan_session: ScanSession) -> KiriScanTask:
        existing = self.get_task(scan_session.id)
        if existing:
            if existing.status in {KiriTaskStatus.FAILED, KiriTaskStatus.EXPIRED} and not existing.source_glb_path:
                existing.provider_serialize = None
                existing.provider_status = None
                existing.status = KiriTaskStatus.QUEUED
                existing.error_message = None
                scan_session.status = ScanStatus.KIRI_PROCESSING
                scan_session.error_message = None
                if scan_session.project:
                    scan_session.project.status = ProjectStatus.PROCESSING
                self.db.commit()
                self.db.refresh(existing)
            return existing
        if not self.settings.kiri_api_token:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Kiri Engine is not configured on the backend.",
            )
        if not self.scan_service.is_ready_for_processing(scan_session):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Upload both required shoe videos before starting Kiri processing.",
            )
        task = KiriScanTask(scan_session_id=scan_session.id, status=KiriTaskStatus.QUEUED)
        self.db.add(task)
        scan_session.status = ScanStatus.KIRI_PROCESSING
        scan_session.error_message = None
        if scan_session.project:
            scan_session.project.status = ProjectStatus.PROCESSING
        self.db.commit()
        self.db.refresh(task)
        return task

    def get_task(self, scan_session_id: str) -> KiriScanTask | None:
        return self.db.scalar(
            select(KiriScanTask).where(KiriScanTask.scan_session_id == scan_session_id)
        )

    def require_task(self, scan_session_id: str) -> KiriScanTask:
        task = self.get_task(scan_session_id)
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kiri task not found.")
        return task

    def start_processing(self, scan_session_id: str) -> None:
        task = self.require_task(scan_session_id)
        scan_session = task.scan_session
        if task.provider_serialize or task.status in TERMINAL_TASK_STATUSES:
            return
        try:
            task.status = KiriTaskStatus.UPLOADING
            self.db.commit()
            with tempfile.TemporaryDirectory(prefix=f"kiri-{scan_session_id}-") as raw_dir:
                work_dir = Path(raw_dir)
                side_path = work_dir / "side-orbit.mp4"
                top_path = work_dir / "top-orbit.mp4"
                merged_path = work_dir / "kiri-scan.mp4"
                side_key = scan_session.side_video_path or scan_session.raw_video_path
                if not side_key or not scan_session.top_video_path:
                    raise KiriError("Both scan video passes are required.")
                side_path.write_bytes(self.storage.get_bytes(side_key))
                top_path.write_bytes(self.storage.get_bytes(scan_session.top_video_path))
                self._merge_videos(side_path, top_path, merged_path)
                task.provider_serialize = self.api.upload_video(merged_path)
            task.status = KiriTaskStatus.PROCESSING
            task.provider_status = "uploading"
            task.error_message = None
            scan_session.status = ScanStatus.KIRI_PROCESSING
            self.db.commit()
        except Exception as exc:
            self._fail(task, str(exc) or "Kiri processing could not be started.")

    def refresh(self, task: KiriScanTask) -> KiriScanTask:
        if not task.provider_serialize or task.status != KiriTaskStatus.PROCESSING:
            return task
        try:
            provider_status = self.api.get_status(task.provider_serialize)
            task.provider_status = provider_status
            if provider_status in PROVIDER_ACTIVE_STATUSES:
                task.error_message = None
                self.db.commit()
                return task
            if provider_status in {"successful", "success", "completed"}:
                self._download_source_glb(task)
                task.status = KiriTaskStatus.READY_FOR_CROP
                task.scan_session.status = ScanStatus.KIRI_READY
                task.error_message = None
            elif provider_status == "expired":
                task.status = KiriTaskStatus.EXPIRED
                task.scan_session.status = ScanStatus.FAILED
                task.error_message = "Kiri asset expired before it was downloaded."
            else:
                self._fail(task, f"Kiri processing failed with status '{provider_status}'.")
                return task
            self.db.commit()
            self.db.refresh(task)
            return task
        except Exception as exc:
            task.error_message = str(exc)[:2000]
            self.db.commit()
            return task

    def set_crop(self, task: KiriScanTask, crop_box: CropBox) -> KiriScanTask:
        if task.status not in {KiriTaskStatus.READY_FOR_CROP, KiriTaskStatus.CROP_CONFIGURED}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Kiri model is not ready for crop configuration.",
            )
        task.crop_box_json = crop_box.model_dump_json(by_alias=True)
        task.status = KiriTaskStatus.CROP_CONFIGURED
        self.db.commit()
        self.db.refresh(task)
        return task

    def queue_save(self, task: KiriScanTask, project_name: str, crop_box: CropBox | None) -> KiriScanTask:
        if task.status == KiriTaskStatus.READY:
            return task
        if crop_box:
            task.crop_box_json = crop_box.model_dump_json(by_alias=True)
        if not task.crop_box_json or not task.source_glb_path:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Configure a crop box after the Kiri model is ready.",
            )
        if task.status not in {
            KiriTaskStatus.READY_FOR_CROP,
            KiriTaskStatus.CROP_CONFIGURED,
            KiriTaskStatus.FAILED,
        }:
            return task
        task.status = KiriTaskStatus.CROP_BAKING
        task.error_message = None
        task.scan_session.status = ScanStatus.CROP_BAKING
        if task.scan_session.project:
            task.scan_session.project.name = project_name.strip()
            task.scan_session.project.status = ProjectStatus.PROCESSING
        self.db.commit()
        self.db.refresh(task)
        return task

    def bake_saved_project(self, scan_session_id: str) -> None:
        task = self.require_task(scan_session_id)
        if task.status == KiriTaskStatus.READY:
            return
        try:
            existing = self.db.scalar(
                select(ModelAsset).where(ModelAsset.scan_session_id == scan_session_id)
            )
            if existing:
                self._mark_ready(task)
                return
            crop_box = self.crop_box(task)
            if not crop_box or not task.source_glb_path:
                raise RuntimeError("Kiri crop configuration is missing.")
            with tempfile.TemporaryDirectory(prefix=f"kiri-crop-{scan_session_id}-") as raw_dir:
                work_dir = Path(raw_dir)
                source_path = work_dir / "source.glb"
                cropped_path = work_dir / "cropped.glb"
                model_dir = work_dir / "model"
                source_path.write_bytes(self.storage.get_bytes(task.source_glb_path))
                self.crop_baker.bake(source_path, cropped_path, crop_box)
                cleanup_report = self.mesh_cleanup.cleanup(
                    cropped_path,
                    model_dir,
                    log_path=model_dir / "kiri-crop-cleanup.log",
                )
                metadata_path = model_dir / "metadata.json"
                metadata_key = task.scan_session.metadata_path
                metadata_path.write_bytes(
                    self.storage.get_bytes(metadata_key) if metadata_key else b"{}"
                )
                quality_path = model_dir / "quality_report.json"
                write_json(
                    quality_path,
                    {
                        "overallScore": cleanup_report.editor_ready_score,
                        "status": "kiri_cropped",
                        "sourceFormat": "glb",
                        "sourceProvider": "kiri",
                        "cropBox": crop_box.model_dump(by_alias=True),
                        "warnings": cleanup_report.cleanup_warnings,
                        **cleanup_report.to_quality_fields(),
                    },
                )
                package_path = model_dir / "shoe_obj_package.zip"
                self._zip_obj_package(model_dir, package_path)
                self.asset_service.create_from_files(
                    scan_session_id,
                    ModelAssetFiles(
                        glb=model_dir / "shoe_preview.glb",
                        obj=model_dir / "shoe.obj",
                        mtl=model_dir / "shoe.mtl",
                        texture=model_dir / "shoe_texture.png",
                        metadata=metadata_path,
                        quality_report=quality_path,
                        obj_package_zip=package_path,
                    ),
                    source_type=ProjectSourceType.SCAN,
                )
            self._mark_ready(task)
        except Exception as exc:
            self._fail(task, str(exc) or "Kiri crop bake failed.")

    def response(self, task: KiriScanTask) -> KiriStatusResponse:
        crop_box = self.crop_box(task)
        model_asset_id = task.scan_session.model_asset.id if task.scan_session.model_asset else None
        preview_url = None
        if task.source_glb_path and task.status not in {KiriTaskStatus.FAILED, KiriTaskStatus.EXPIRED}:
            ticket = create_kiri_preview_ticket(task.scan_session_id)
            preview_url = (
                f"/api/scan-sessions/{task.scan_session_id}/kiri/preview?ticket={ticket}"
            )
        return KiriStatusResponse(
            scanSessionId=task.scan_session_id,
            projectId=task.scan_session.project_id,
            status=task.status,
            providerStatus=task.provider_status,
            progress=self.progress(task.status),
            previewUrl=preview_url,
            cropBox=crop_box,
            modelAssetId=model_asset_id,
            errorMessage=task.error_message,
            updatedAt=task.updated_at,
        )

    @staticmethod
    def progress(task_status: str) -> int:
        return {
            KiriTaskStatus.QUEUED: 5,
            KiriTaskStatus.UPLOADING: 15,
            KiriTaskStatus.PROCESSING: 55,
            KiriTaskStatus.READY_FOR_CROP: 75,
            KiriTaskStatus.CROP_CONFIGURED: 80,
            KiriTaskStatus.CROP_BAKING: 90,
            KiriTaskStatus.READY: 100,
            KiriTaskStatus.FAILED: 0,
            KiriTaskStatus.EXPIRED: 0,
        }.get(task_status, 0)

    @staticmethod
    def crop_box(task: KiriScanTask) -> CropBox | None:
        if not task.crop_box_json:
            return None
        return CropBox.model_validate_json(task.crop_box_json)

    def _merge_videos(self, side_path: Path, top_path: Path, output_path: Path) -> None:
        scale_filter = (
            "scale=1920:1080:force_original_aspect_ratio=decrease,"
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
        )
        result = self.runner.run(
            [
                self.settings.ffmpeg_bin,
                "-y",
                "-i",
                str(side_path),
                "-i",
                str(top_path),
                "-filter_complex",
                f"[0:v]{scale_filter}[v0];[1:v]{scale_filter}[v1];"
                "[v0][v1]concat=n=2:v=1:a=0[outv]",
                "-map",
                "[outv]",
                "-t",
                "180",
                "-r",
                "30",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(output_path),
            ],
            log_path=output_path.parent / "ffmpeg-merge.log",
            timeout=self.settings.kiri_request_timeout_seconds,
        )
        if not result.ok or not output_path.is_file():
            message = result.stderr.strip() or result.stdout.strip() or "FFmpeg merge failed."
            raise KiriError(f"Could not prepare Kiri video: {message[-1200:]}")

    def _download_source_glb(self, task: KiriScanTask) -> None:
        if task.source_glb_path and self.storage.exists(task.source_glb_path):
            return
        if not task.provider_serialize:
            raise KiriError("Kiri serialize id is missing.")
        zip_url = self.api.get_model_zip_url(task.provider_serialize)
        zip_bytes = self.api.download_model_zip(zip_url)
        glb_bytes = self._extract_glb(zip_bytes)
        stored = self.storage.put_bytes(
            f"kiri/{task.scan_session_id}/source.glb",
            glb_bytes,
            "model/gltf-binary",
        )
        task.source_glb_path = stored.key

    def _extract_glb(self, zip_bytes: bytes) -> bytes:
        max_bytes = self.settings.kiri_max_download_size_mb * 1024 * 1024
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
                candidates = []
                total = 0
                for item in archive.infolist():
                    if item.is_dir():
                        continue
                    path = PurePosixPath(item.filename)
                    if path.is_absolute() or ".." in path.parts:
                        raise KiriError("Kiri ZIP contains an unsafe path.")
                    total += item.file_size
                    if total > max_bytes:
                        raise KiriError("Kiri ZIP is too large after extraction.")
                    if path.suffix.lower() == ".glb":
                        candidates.append(item)
                if not candidates:
                    raise KiriError("Kiri ZIP does not contain a GLB model.")
                candidate = sorted(candidates, key=lambda item: (len(item.filename), item.filename))[0]
                glb_bytes = archive.read(candidate)
        except zipfile.BadZipFile as exc:
            raise KiriError("Kiri returned an invalid model ZIP.") from exc
        if not glb_bytes.startswith(b"glTF"):
            raise KiriError("Kiri ZIP contains an invalid GLB model.")
        return glb_bytes

    @staticmethod
    def _zip_obj_package(model_dir: Path, zip_path: Path) -> None:
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in [
                "shoe.obj",
                "shoe.mtl",
                "shoe_texture.png",
                "metadata.json",
                "quality_report.json",
            ]:
                archive.write(model_dir / name, name)

    def _mark_ready(self, task: KiriScanTask) -> None:
        task.status = KiriTaskStatus.READY
        task.error_message = None
        task.scan_session.status = ScanStatus.CROP_READY
        task.scan_session.error_message = None
        if task.scan_session.project:
            task.scan_session.project.status = ProjectStatus.READY
        self.db.commit()

    def _fail(self, task: KiriScanTask, message: str) -> None:
        safe_message = message[:2000]
        task.status = KiriTaskStatus.FAILED
        task.error_message = safe_message
        task.scan_session.status = ScanStatus.FAILED
        task.scan_session.error_message = safe_message
        if task.scan_session.project:
            task.scan_session.project.status = ProjectStatus.FAILED
        self.db.commit()
