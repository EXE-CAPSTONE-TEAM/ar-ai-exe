from __future__ import annotations

import shutil
import tempfile
import zipfile
from datetime import UTC, datetime
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
from app.services.control_plane_mobile import ControlPlaneMobileClient
from app.services.crop_baker import CropBakeService
from app.services.kiri_client import KiriApiClient, KiriError
from app.services.mesh_cleanup import MeshCleanupService
from app.services.model_assets import ModelAssetService
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
        control_plane: ControlPlaneMobileClient | None = None,
    ) -> None:
        self.db = db
        self.settings = get_settings()
        self.api = api or KiriApiClient()
        self.storage = storage or get_storage_service()
        self.runner = runner or CommandRunner()
        self.crop_baker = crop_baker or CropBakeService()
        self.mesh_cleanup = mesh_cleanup or MeshCleanupService()
        self.control_plane = control_plane or ControlPlaneMobileClient()
        self.asset_service = ModelAssetService(db, storage=self.storage)
        self.scan_service = ScanSessionService(db)

    def create_task(self, scan_session: ScanSession) -> KiriScanTask:
        existing = self.get_task(scan_session.id)
        if existing:
            if (
                existing.status in {KiriTaskStatus.FAILED, KiriTaskStatus.EXPIRED}
                and not existing.source_glb_path
            ):
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
                detail="Upload scan video before starting Kiri processing.",
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Kiri task not found."
            )
        return task

    def start_processing(self, scan_session_id: str) -> None:
        task = self.require_task(scan_session_id)
        scan_session = task.scan_session
        if task.provider_serialize or task.status in TERMINAL_TASK_STATUSES:
            return
        video_key = scan_session.raw_video_path or scan_session.side_video_path
        if not video_key:
            self._fail(task, "Scan video is required.")
            return
        try:
            task.status = KiriTaskStatus.UPLOADING
            self.db.commit()
            temp_dir = tempfile.mkdtemp(prefix=f"kiri-{scan_session_id}-")
            try:
                work_dir = Path(temp_dir)
                video_path = work_dir / "scan.mp4"
                self.storage.download_to(video_key, video_path)
                task.provider_serialize = self.api.upload_video(video_path)
                # Delete temp video and the R2 video once KIRI accepts it
                if video_path.exists():
                    video_path.unlink()
                self.storage.delete(video_key)
                scan_session.raw_video_path = None
                scan_session.side_video_path = None
                scan_session.top_video_path = None
                self.db.commit()
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

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

    def queue_save(
        self,
        task: KiriScanTask,
        project_name: str,
        crop_box: CropBox | None = None,
    ) -> KiriScanTask:
        if task.status == KiriTaskStatus.READY:
            return task
        normalized_project_name = project_name.strip()
        if task.scan_session.control_plane_project_id and len(normalized_project_name) > 100:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Canonical project name must contain at most 100 characters.",
            )
        if not task.source_glb_path:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Kiri model is not ready.",
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
        if task.scan_session.control_plane_project_id:
            task.scan_session.control_plane_project_name = normalized_project_name
        if task.scan_session.project:
            task.scan_session.project.name = normalized_project_name
            task.scan_session.project.status = ProjectStatus.PROCESSING
        self.db.commit()
        self.db.refresh(task)
        return task

    def publish_saved_project(self, scan_session_id: str) -> None:
        task = self.require_task(scan_session_id)
        if task.status == KiriTaskStatus.READY:
            return
        try:
            if not task.source_glb_path or not self.storage.exists(task.source_glb_path):
                self._download_source_glb(task)
            if not task.source_glb_path or not self.storage.exists(task.source_glb_path):
                raise RuntimeError("Kiri source GLB is missing.")

            scan_session = task.scan_session
            head_info = self.storage.head(task.source_glb_path)
            glb_size = head_info.get("content_length", 0) if head_info else 0
            if not glb_size:
                temp_dir = tempfile.mkdtemp(prefix=f"kiri-size-{scan_session_id}-")
                try:
                    temp_glb = Path(temp_dir) / "source.glb"
                    self.storage.download_to(task.source_glb_path, temp_glb)
                    glb_size = temp_glb.stat().st_size
                finally:
                    shutil.rmtree(temp_dir, ignore_errors=True)

            if scan_session.control_plane_project_id:
                self._publish_control_plane_model(
                    task,
                    glb_path=task.source_glb_path,
                    glb_size_bytes=glb_size,
                )
            elif scan_session.project_id:
                existing = self.db.scalar(
                    select(ModelAsset).where(ModelAsset.scan_session_id == scan_session_id)
                )
                if not existing:
                    existing = ModelAsset(
                        scan_session_id=scan_session_id,
                        glb_path=task.source_glb_path,
                        obj_path="",
                        mtl_path="",
                        texture_path="",
                        quality_report_path="",
                        glb_size_bytes=glb_size,
                        glb_content_type="model/gltf-binary",
                        source_type=ProjectSourceType.SCAN,
                        status=ScanStatus.COMPLETED,
                    )
                    self.db.add(existing)
                    self.db.commit()

            self._mark_ready(task)
        except Exception as exc:
            self._fail(task, str(exc) or "Kiri publish failed.")

    bake_saved_project = publish_saved_project

    def response(self, task: KiriScanTask) -> KiriStatusResponse:
        crop_box = self.crop_box(task)
        model_asset_id = task.scan_session.control_plane_model_asset_id
        if not model_asset_id and task.scan_session.model_asset:
            model_asset_id = task.scan_session.model_asset.id
        project_id = task.scan_session.control_plane_project_id or task.scan_session.project_id
        preview_url = None
        if task.source_glb_path and task.status not in {
            KiriTaskStatus.FAILED,
            KiriTaskStatus.EXPIRED,
        }:
            ticket = create_kiri_preview_ticket(task.scan_session_id)
            preview_url = f"/api/scan-sessions/{task.scan_session_id}/kiri/preview?ticket={ticket}"
        return KiriStatusResponse(
            scanSessionId=task.scan_session_id,
            projectId=project_id,
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

    def _download_source_glb(self, task: KiriScanTask) -> None:
        if task.source_glb_path and self.storage.exists(task.source_glb_path):
            return
        if not task.provider_serialize:
            raise KiriError("Kiri serialize id is missing.")
        zip_url = self.api.get_model_zip_url(task.provider_serialize)
        temp_dir = tempfile.mkdtemp(prefix=f"kiri-zip-{task.scan_session_id}-")
        try:
            work_dir = Path(temp_dir)
            zip_path = work_dir / "model.zip"
            glb_path = work_dir / "source.glb"
            self.api.download_model_zip_to(zip_url, zip_path)
            self._extract_glb_from_zip(zip_path, glb_path)
            zip_path.unlink(missing_ok=True)
            stored = self.storage.put_file(
                f"kiri/{task.scan_session_id}/source.glb",
                glb_path,
                "model/gltf-binary",
            )
            task.source_glb_path = stored.key
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _extract_glb_from_zip(self, zip_path: Path, output_glb_path: Path) -> None:
        max_bytes = self.settings.kiri_max_download_size_mb * 1024 * 1024
        try:
            with zipfile.ZipFile(zip_path) as archive:
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
                candidate = sorted(
                    candidates, key=lambda item: (len(item.filename), item.filename)
                )[0]
                with archive.open(candidate) as src, output_glb_path.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
        except zipfile.BadZipFile as exc:
            raise KiriError("Kiri returned an invalid model ZIP.") from exc

        with output_glb_path.open("rb") as f:
            magic = f.read(4)
        if magic != b"glTF":
            raise KiriError("Kiri ZIP contains an invalid GLB model.")

    def _publish_control_plane_model(
        self,
        task: KiriScanTask,
        *,
        glb_path: str,
        glb_size_bytes: int,
    ) -> None:
        scan_session = task.scan_session
        project_id = scan_session.control_plane_project_id
        if not project_id:
            return
        if (
            not scan_session.control_plane_user_id
            or not scan_session.control_plane_completion_token
        ):
            raise RuntimeError("Canonical scan ownership is incomplete.")
        if scan_session.control_plane_model_asset_id and scan_session.control_plane_published_at:
            return
        if not glb_size_bytes:
            raise RuntimeError("Generated GLB size metadata is missing.")

        result = self.control_plane.publish_glb(
            completion_token=scan_session.control_plane_completion_token,
            expected_project_id=project_id,
            project_name=scan_session.control_plane_project_name or "Untitled shoe scan",
            web_project_url=scan_session.web_design_url or "",
            file_size_bytes=glb_size_bytes,
            chunks=self.storage.iter_bytes(glb_path),
        )
        if result.project_id != project_id or result.status not in {"raw", "ready"}:
            raise RuntimeError("Control-plane publish result is inconsistent.")

        scan_session.control_plane_model_asset_id = result.model_asset_id
        scan_session.control_plane_published_at = datetime.now(UTC).replace(tzinfo=None)
        scan_session.web_design_url = result.web_project_url
        self.db.commit()

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
