from typing import Annotated

import jwt
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    HTTPException,
    Query,
    status,
)
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.scan_deps import ScanActor, get_scan_actor
from app.core.config import get_settings
from app.core.scan_identity import ControlPlaneScanPrincipal
from app.core.security import decode_kiri_preview_ticket
from app.db.database import get_db
from app.models import KiriTaskStatus, ProjectStatus, ScanSession, ScanStatus
from app.schemas.scan import (
    KiriStatusResponse,
    SaveKiriProjectRequest,
    ScanMetadata,
    ScanSessionCreate,
    ScanSessionResponse,
    ScanStatusResponse,
    ScanUploadResponse,
    VideoUploadUrlResponse,
    VideoUploadedRequest,
)
from app.services.kiri_pipeline import KiriPipelineService
from app.services.reconstruction_toolchain import ReconstructionToolchainService
from app.services.scan_metadata import parse_scan_metadata
from app.services.scan_sessions import ScanSessionService
from app.services.storage import StorageService, get_storage_service
from app.workers.kiri_worker import bake_kiri_project, start_kiri_processing
from app.workers.reconstruction_worker import process_scan_session


router = APIRouter(prefix="/scan-sessions", tags=["scan-sessions"])

ACTIVE_PROCESSING_STATUSES = {
    ScanStatus.QUEUED,
    ScanStatus.EXTRACTING_FRAMES,
    ScanStatus.FILTERING_FRAMES,
    ScanStatus.PREPARING_RECONSTRUCTION,
    ScanStatus.RECONSTRUCTING,
    ScanStatus.CLEANING_MESH,
    ScanStatus.UV_UNWRAPPING,
    ScanStatus.TEXTURE_BAKING,
    ScanStatus.EXPORTING,
    ScanStatus.KIRI_PROCESSING,
    ScanStatus.CROP_BAKING,
}


def scan_response(scan_session: ScanSession, model_asset_id: str | None) -> ScanSessionResponse:
    user_id = scan_session.control_plane_user_id or scan_session.user_id
    project_id = scan_session.control_plane_project_id or scan_session.project_id
    if not user_id:
        raise RuntimeError("Scan session owner invariant is violated.")
    web_design_url = scan_session.web_design_url
    if not web_design_url:
        web_design_url = (
            f"{get_settings().web_app_base_url.rstrip('/')}/editor/{project_id}"
            if project_id
            else f"{get_settings().web_app_base_url.rstrip('/')}/design?scanId={scan_session.id}"
        )
    return ScanSessionResponse(
        id=scan_session.id,
        userId=user_id,
        projectId=project_id,
        status=scan_session.status,
        sourceType=scan_session.source_type,
        importName=scan_session.import_name,
        errorMessage=scan_session.error_message,
        modelAssetId=model_asset_id,
        webDesignUrl=web_design_url,
        uploadedPasses=ScanSessionService.uploaded_passes(scan_session),
        requiredPasses=ScanSessionService.required_passes_for(scan_session),
        createdAt=scan_session.created_at,
        updatedAt=scan_session.updated_at,
    )


def status_response(scan_session: ScanSession, service: ScanSessionService) -> ScanStatusResponse:
    return ScanStatusResponse(
        id=scan_session.id,
        projectId=scan_session.control_plane_project_id or scan_session.project_id,
        status=scan_session.status,
        errorMessage=scan_session.error_message,
        sourceType=scan_session.source_type,
        importName=scan_session.import_name,
        modelAssetId=service.get_model_asset_id(scan_session.id),
        updatedAt=scan_session.updated_at,
        uploadedPasses=service.uploaded_passes(scan_session),
        requiredPasses=service.required_passes_for(scan_session),
        readyForProcessing=service.is_ready_for_processing(scan_session),
        processingStarted=scan_session.status in ACTIVE_PROCESSING_STATUSES,
        webDesignUrl=scan_session.web_design_url
        or service.web_design_url(scan_session.id, scan_session.project_id),
    )


@router.post("", response_model=ScanSessionResponse, status_code=status.HTTP_201_CREATED)
def create_scan_session(
    scan_actor: Annotated[ScanActor, Depends(get_scan_actor)],
    db: Annotated[Session, Depends(get_db)],
    payload: Annotated[ScanSessionCreate | None, Body()] = None,
) -> ScanSessionResponse:
    service = ScanSessionService(db)
    if isinstance(scan_actor, ControlPlaneScanPrincipal):
        if payload and payload.project_id and payload.project_id != scan_actor.project_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Scan token does not grant access to that project.",
            )
        scan_session = service.create_control_plane(
            scan_actor,
            payload.metadata if payload else None,
        )
    else:
        scan_session = service.create(
            scan_actor,
            payload.metadata if payload else None,
            payload.project_id if payload else None,
        )
    return scan_response(scan_session, None)


@router.post("/{scan_session_id}/video-upload-url", response_model=VideoUploadUrlResponse)
def get_video_upload_url(
    scan_session_id: str,
    scan_actor: Annotated[ScanActor, Depends(get_scan_actor)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[StorageService, Depends(get_storage_service)],
) -> VideoUploadUrlResponse:
    service = ScanSessionService(db, storage=storage)
    scan_session = service.get_for_actor(scan_session_id, scan_actor)
    key = f"raw-scans/{scan_session_id}/scan.mp4"
    settings = get_settings()
    ttl = settings.signed_url_ttl_seconds
    upload_url = storage.create_upload_url(
        key,
        content_type="video/mp4",
        expires_in=ttl,
    )
    scan_session.raw_video_path = key
    scan_session.side_video_path = key
    db.commit()
    return VideoUploadUrlResponse(
        uploadUrl=upload_url,
        key=key,
        expiresIn=ttl,
    )


@router.post("/{scan_session_id}/video-uploaded", response_model=ScanUploadResponse)
def video_uploaded(
    scan_session_id: str,
    scan_actor: Annotated[ScanActor, Depends(get_scan_actor)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[StorageService, Depends(get_storage_service)],
    payload: Annotated[VideoUploadedRequest | None, Body()] = None,
) -> ScanUploadResponse:
    service = ScanSessionService(db, storage=storage)
    scan_session = service.get_for_actor(scan_session_id, scan_actor)
    key = (
        (payload.key if payload and payload.key else None)
        or scan_session.raw_video_path
        or f"raw-scans/{scan_session_id}/scan.mp4"
    )
    head_info = storage.head(key)
    if not head_info:
        storage.delete(key)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Uploaded video not found in storage.",
        )
    size = head_info.get("content_length", 0)
    max_bytes = get_settings().max_upload_size_mb * 1024 * 1024
    if size <= 0 or size > max_bytes:
        storage.delete(key)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Uploaded video must be between 1 byte and {get_settings().max_upload_size_mb} MB.",
        )
    scan_session.raw_video_path = key
    scan_session.side_video_path = key
    scan_session.raw_video_size_bytes = size
    scan_session.side_video_size_bytes = size
    scan_session.status = ScanStatus.UPLOADED
    scan_session.error_message = None
    if scan_session.project:
        scan_session.project.status = ProjectStatus.PROCESSING
    db.commit()
    db.refresh(scan_session)
    return ScanUploadResponse(
        scanSession=scan_response(scan_session, service.get_model_asset_id(scan_session.id)),
        passType="side_orbit",
        uploadedPasses=service.uploaded_passes(scan_session),
        requiredPasses=list(service.required_passes),
        readyForProcessing=service.is_ready_for_processing(scan_session),
        processingStarted=False,
        webDesignUrl=scan_session.web_design_url or service.web_design_url(scan_session.id),
    )


@router.get("/{scan_session_id}", response_model=ScanSessionResponse)
def get_scan_session(
    scan_session_id: str,
    scan_actor: Annotated[ScanActor, Depends(get_scan_actor)],
    db: Annotated[Session, Depends(get_db)],
) -> ScanSessionResponse:
    service = ScanSessionService(db)
    scan_session = service.get_for_actor(scan_session_id, scan_actor)
    return scan_response(scan_session, service.get_model_asset_id(scan_session.id))


@router.get("/{scan_session_id}/status", response_model=ScanStatusResponse)
def get_scan_status(
    scan_session_id: str,
    scan_actor: Annotated[ScanActor, Depends(get_scan_actor)],
    db: Annotated[Session, Depends(get_db)],
) -> ScanStatusResponse:
    service = ScanSessionService(db)
    scan_session = service.get_for_actor(scan_session_id, scan_actor)
    return status_response(scan_session, service)


@router.post("/{scan_session_id}/kiri/process", response_model=KiriStatusResponse)
def process_scan_with_kiri(
    scan_session_id: str,
    background_tasks: BackgroundTasks,
    scan_actor: Annotated[ScanActor, Depends(get_scan_actor)],
    db: Annotated[Session, Depends(get_db)],
) -> KiriStatusResponse:
    scan_session = ScanSessionService(db).get_for_actor(scan_session_id, scan_actor)
    service = KiriPipelineService(db)
    task = service.create_task(scan_session)
    if task.status == KiriTaskStatus.QUEUED:
        background_tasks.add_task(start_kiri_processing, scan_session_id)
    return service.response(task)


@router.get("/{scan_session_id}/kiri/status", response_model=KiriStatusResponse)
def get_kiri_status(
    scan_session_id: str,
    scan_actor: Annotated[ScanActor, Depends(get_scan_actor)],
    db: Annotated[Session, Depends(get_db)],
) -> KiriStatusResponse:
    ScanSessionService(db).get_for_actor(scan_session_id, scan_actor)
    service = KiriPipelineService(db)
    task = service.refresh(service.require_task(scan_session_id))
    return service.response(task)


@router.post("/{scan_session_id}/save-project", response_model=KiriStatusResponse)
def save_kiri_project(
    scan_session_id: str,
    payload: SaveKiriProjectRequest,
    background_tasks: BackgroundTasks,
    scan_actor: Annotated[ScanActor, Depends(get_scan_actor)],
    db: Annotated[Session, Depends(get_db)],
) -> KiriStatusResponse:
    ScanSessionService(db).get_for_actor(scan_session_id, scan_actor)
    service = KiriPipelineService(db)
    task = service.queue_save(
        service.require_task(scan_session_id),
        payload.project_name,
    )
    if task.status == KiriTaskStatus.CROP_BAKING:
        background_tasks.add_task(bake_kiri_project, scan_session_id)
    return service.response(task)


@router.get("/{scan_session_id}/kiri/preview")
def get_kiri_preview(
    scan_session_id: str,
    db: Annotated[Session, Depends(get_db)],
    ticket: Annotated[str, Query(min_length=1)],
    storage: Annotated[StorageService, Depends(get_storage_service)],
) -> RedirectResponse:
    try:
        ticket_scan_id = decode_kiri_preview_ticket(ticket)
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid preview ticket."
        ) from exc
    if ticket_scan_id != scan_session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid preview ticket."
        )
    service = KiriPipelineService(db, storage=storage)
    task = service.require_task(scan_session_id)
    if not task.source_glb_path or not storage.exists(task.source_glb_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kiri preview not found.")
    signed_url = storage.create_signed_url(
        task.source_glb_path,
        expires_in=get_settings().signed_url_ttl_seconds,
    )
    if not signed_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kiri preview URL could not be generated.",
        )
    return RedirectResponse(
        url=signed_url,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


@router.post("/{scan_session_id}/process", response_model=ScanStatusResponse)
def process_scan(
    scan_session_id: str,
    background_tasks: BackgroundTasks,
    scan_actor: Annotated[ScanActor, Depends(get_scan_actor)],
    db: Annotated[Session, Depends(get_db)],
) -> ScanStatusResponse:
    service = ScanSessionService(db)
    scan_session = service.get_for_actor(scan_session_id, scan_actor)
    if not service.is_ready_for_processing(scan_session):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload both required shoe videos before starting processing.",
        )
    if (
        scan_session.status in ACTIVE_PROCESSING_STATUSES
        or scan_session.status == ScanStatus.COMPLETED
    ):
        return status_response(scan_session, service)

    readiness = ReconstructionToolchainService().check()
    if not readiness.ready:
        blocked_session = service.set_status(
            scan_session.id,
            ScanStatus.TOOLCHAIN_UNAVAILABLE,
            readiness.message,
        )
        return status_response(blocked_session, service)

    queued_session = service.set_status(scan_session.id, ScanStatus.QUEUED)
    background_tasks.add_task(process_scan_session, scan_session.id)
    return status_response(queued_session, service)


def parse_metadata(raw_metadata: str) -> ScanMetadata:
    return parse_scan_metadata(raw_metadata)
