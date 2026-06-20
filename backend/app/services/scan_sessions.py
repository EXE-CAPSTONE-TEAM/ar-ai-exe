from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    ModelAsset,
    Project,
    ProjectSourceType,
    ProjectStatus,
    ScanSession,
    ScanSource,
    ScanStatus,
    User,
)
from app.schemas.scan import ScanMetadata
from app.services.scan_metadata import scan_metadata_bytes
from app.services.storage import get_storage_service


class ScanSessionService:
    allowed_content_types = {"video/mp4"}
    allowed_extensions = {".mp4"}
    required_passes = ("side_orbit", "top_orbit")
    pass_aliases = {
        "side-orbit": "side_orbit",
        "side_orbit": "side_orbit",
        "top-orbit": "top_orbit",
        "top_orbit": "top_orbit",
    }

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.storage = get_storage_service()

    def create(
        self,
        user: User,
        metadata: ScanMetadata | None = None,
        project_id: str | None = None,
    ) -> ScanSession:
        project = self._project_for_scan(
            user,
            project_id=project_id,
            fallback_name="Untitled shoe scan",
            source_type=ProjectSourceType.SCAN,
        )
        scan_session = ScanSession(user_id=user.id, project_id=project.id)
        self.db.add(scan_session)
        self.db.flush()
        scan_session.web_design_url = self.web_design_url(scan_session.id, project.id)

        if metadata:
            metadata_object = self.storage.put_bytes(
                self._metadata_key(scan_session.id),
                scan_metadata_bytes(metadata),
                "application/json",
            )
            scan_session.metadata_path = metadata_object.key
            scan_session.metadata_size_bytes = metadata_object.size_bytes
            scan_session.metadata_content_type = metadata_object.content_type
            scan_session.metadata_checksum = metadata_object.checksum

        self.db.commit()
        self.db.refresh(scan_session)
        return scan_session

    def get_for_user(self, scan_session_id: str, user: User) -> ScanSession:
        scan_session = self.db.get(ScanSession, scan_session_id)
        if not scan_session or scan_session.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan session not found.")
        return scan_session

    def get_model_asset_id(self, scan_session_id: str) -> str | None:
        asset = self.db.scalar(select(ModelAsset).where(ModelAsset.scan_session_id == scan_session_id))
        return asset.id if asset else None

    @classmethod
    def uploaded_passes(cls, scan_session: ScanSession) -> list[str]:
        if scan_session.source_type == ScanSource.IMPORT:
            return []
        uploaded: list[str] = []
        if scan_session.side_video_path or scan_session.raw_video_path:
            uploaded.append("side_orbit")
        if scan_session.top_video_path:
            uploaded.append("top_orbit")
        return uploaded

    @classmethod
    def is_ready_for_processing(cls, scan_session: ScanSession) -> bool:
        if scan_session.source_type == ScanSource.IMPORT:
            return scan_session.status == ScanStatus.COMPLETED
        return all(pass_type in cls.uploaded_passes(scan_session) for pass_type in cls.required_passes)

    @classmethod
    def required_passes_for(cls, scan_session: ScanSession) -> list[str]:
        if scan_session.source_type == ScanSource.IMPORT:
            return []
        return list(cls.required_passes)

    def normalize_pass_type(self, pass_type: str) -> str:
        normalized = self.pass_aliases.get(pass_type)
        if not normalized:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported video pass. Use 'side-orbit' or 'top-orbit'.",
            )
        return normalized

    def save_upload(
        self,
        scan_session: ScanSession,
        file_name: str | None,
        content_type: str | None,
        video_bytes: bytes,
        metadata: ScanMetadata,
    ) -> ScanSession:
        return self.save_pass_upload(
            scan_session=scan_session,
            pass_type="side_orbit",
            file_name=file_name,
            content_type=content_type,
            video_bytes=video_bytes,
            metadata=metadata,
        )

    def save_pass_upload(
        self,
        scan_session: ScanSession,
        pass_type: str,
        file_name: str | None,
        content_type: str | None,
        video_bytes: bytes,
        metadata: ScanMetadata | None = None,
    ) -> ScanSession:
        normalized_pass = self.normalize_pass_type(pass_type)
        self._validate_video(file_name, content_type, video_bytes)
        video_object = self.storage.put_bytes(
            self._raw_video_key(scan_session.id, normalized_pass),
            video_bytes,
            content_type or "video/mp4",
        )

        if normalized_pass == "side_orbit":
            scan_session.side_video_path = video_object.key
            scan_session.side_video_size_bytes = video_object.size_bytes
            scan_session.side_video_content_type = video_object.content_type
            scan_session.side_video_checksum = video_object.checksum
            scan_session.raw_video_path = video_object.key
            scan_session.raw_video_size_bytes = video_object.size_bytes
            scan_session.raw_video_content_type = video_object.content_type
            scan_session.raw_video_checksum = video_object.checksum
        else:
            scan_session.top_video_path = video_object.key
            scan_session.top_video_size_bytes = video_object.size_bytes
            scan_session.top_video_content_type = video_object.content_type
            scan_session.top_video_checksum = video_object.checksum

        if metadata:
            metadata_object = self.storage.put_bytes(
                self._metadata_key(scan_session.id),
                scan_metadata_bytes(metadata),
                "application/json",
            )
            scan_session.metadata_path = metadata_object.key
            scan_session.metadata_size_bytes = metadata_object.size_bytes
            scan_session.metadata_content_type = metadata_object.content_type
            scan_session.metadata_checksum = metadata_object.checksum

        scan_session.web_design_url = self.web_design_url(scan_session.id, scan_session.project_id)
        scan_session.status = (
            ScanStatus.UPLOADED if self.is_ready_for_processing(scan_session) else ScanStatus.WAITING_FOR_UPLOADS
        )
        if scan_session.project:
            scan_session.project.status = ProjectStatus.PROCESSING
        scan_session.error_message = None
        self.db.commit()
        self.db.refresh(scan_session)
        return scan_session

    def save_metadata(self, scan_session: ScanSession, metadata: ScanMetadata) -> ScanSession:
        metadata_object = self.storage.put_bytes(
            self._metadata_key(scan_session.id),
            scan_metadata_bytes(metadata),
            "application/json",
        )
        scan_session.metadata_path = metadata_object.key
        scan_session.metadata_size_bytes = metadata_object.size_bytes
        scan_session.metadata_content_type = metadata_object.content_type
        scan_session.metadata_checksum = metadata_object.checksum
        scan_session.web_design_url = self.web_design_url(scan_session.id, scan_session.project_id)
        scan_session.error_message = None
        self.db.commit()
        self.db.refresh(scan_session)
        return scan_session

    def set_status(
        self,
        scan_session_id: str,
        status_value: str,
        error_message: str | None = None,
    ) -> ScanSession:
        scan_session = self.db.get(ScanSession, scan_session_id)
        if not scan_session:
            raise ValueError(f"Scan session {scan_session_id} not found.")
        scan_session.status = status_value
        scan_session.error_message = error_message
        if scan_session.project:
            scan_session.project.status = self._project_status_from_scan_status(status_value)
        self.db.commit()
        self.db.refresh(scan_session)
        return scan_session

    def web_design_url(self, scan_session_id: str, project_id: str | None = None) -> str:
        if project_id:
            return f"{self.settings.web_app_base_url.rstrip('/')}/editor/{project_id}"
        return f"{self.settings.web_app_base_url.rstrip('/')}/design?scanId={scan_session_id}"

    def _project_for_scan(
        self,
        user: User,
        project_id: str | None,
        fallback_name: str,
        source_type: str,
    ) -> Project:
        if project_id:
            project = self.db.get(Project, project_id)
            if not project or project.user_id != user.id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
            return project

        project = Project(
            user_id=user.id,
            name=fallback_name,
            status=ProjectStatus.DRAFT,
            source_type=source_type,
        )
        self.db.add(project)
        self.db.flush()
        return project

    def _project_status_from_scan_status(self, status_value: str) -> str:
        if status_value == ScanStatus.COMPLETED:
            return ProjectStatus.READY
        if status_value == ScanStatus.FAILED:
            return ProjectStatus.FAILED
        if status_value == ScanStatus.CREATED:
            return ProjectStatus.DRAFT
        if status_value in {ScanStatus.WAITING_FOR_UPLOADS, ScanStatus.UPLOADED}:
            return ProjectStatus.PROCESSING
        return ProjectStatus.PROCESSING

    def _raw_video_key(self, scan_session_id: str, pass_type: str) -> str:
        file_name = "side_orbit.mp4" if pass_type == "side_orbit" else "top_orbit.mp4"
        return f"raw-scans/{scan_session_id}/{file_name}"

    def _metadata_key(self, scan_session_id: str) -> str:
        return f"raw-scans/{scan_session_id}/metadata.json"

    def _validate_video(
        self,
        file_name: str | None,
        content_type: str | None,
        video_bytes: bytes,
    ) -> None:
        suffix = Path(file_name or "").suffix.lower()
        if content_type not in self.allowed_content_types and suffix not in self.allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid video file. Upload an MP4 file using field name 'video'.",
            )

        if not video_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded video is empty.",
            )

        max_bytes = self.settings.max_upload_size_mb * 1024 * 1024
        if len(video_bytes) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"Uploaded video exceeds {self.settings.max_upload_size_mb} MB.",
            )
