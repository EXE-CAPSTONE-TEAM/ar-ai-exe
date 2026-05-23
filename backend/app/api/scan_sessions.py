from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.database import get_db
from app.models import ScanSession, ScanStatus, User
from app.schemas.scan import (
    ScanMetadata,
    ScanSessionCreate,
    ScanSessionResponse,
    ScanStatusResponse,
    ScanUploadResponse,
)
from app.services.reconstruction_toolchain import ReconstructionToolchainService
from app.services.scan_metadata import parse_scan_metadata
from app.services.scan_sessions import ScanSessionService
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
}


def scan_response(scan_session: ScanSession, model_asset_id: str | None) -> ScanSessionResponse:
    payload = ScanSessionResponse.model_validate(scan_session).model_dump()
    payload["model_asset_id"] = model_asset_id
    payload["uploaded_passes"] = ScanSessionService.uploaded_passes(scan_session)
    payload["required_passes"] = ScanSessionService.required_passes_for(scan_session)
    if not payload.get("web_design_url"):
        payload["web_design_url"] = f"{get_settings().web_app_base_url.rstrip('/')}/design?scanId={scan_session.id}"
    return ScanSessionResponse.model_validate(payload)


def status_response(scan_session: ScanSession, service: ScanSessionService) -> ScanStatusResponse:
    return ScanStatusResponse(
        id=scan_session.id,
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
        webDesignUrl=scan_session.web_design_url or service.web_design_url(scan_session.id),
    )


@router.post("", response_model=ScanSessionResponse, status_code=status.HTTP_201_CREATED)
def create_scan_session(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    payload: Annotated[ScanSessionCreate | None, Body()] = None,
) -> ScanSessionResponse:
    scan_session = ScanSessionService(db).create(current_user, payload.metadata if payload else None)
    return scan_response(scan_session, None)


@router.post("/{scan_session_id}/upload-video", response_model=ScanUploadResponse)
async def upload_video(
    scan_session_id: str,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    metadata: Annotated[str, Form()],
    video: Annotated[UploadFile, File()],
) -> ScanUploadResponse:
    service = ScanSessionService(db)
    scan_session = service.get_for_user(scan_session_id, current_user)
    parsed_metadata = parse_metadata(metadata)
    saved_session = service.save_upload(
        scan_session=scan_session,
        file_name=video.filename,
        content_type=video.content_type,
        video_bytes=await video.read(),
        metadata=parsed_metadata,
    )
    return ScanUploadResponse(
        scanSession=scan_response(saved_session, service.get_model_asset_id(saved_session.id)),
        passType="side_orbit",
        uploadedPasses=service.uploaded_passes(saved_session),
        requiredPasses=list(service.required_passes),
        readyForProcessing=service.is_ready_for_processing(saved_session),
        processingStarted=False,
        webDesignUrl=saved_session.web_design_url or service.web_design_url(saved_session.id),
    )


@router.post("/{scan_session_id}/videos/{pass_type}", response_model=ScanUploadResponse)
async def upload_video_pass(
    scan_session_id: str,
    pass_type: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    video: Annotated[UploadFile, File()],
    metadata: Annotated[str | None, Form()] = None,
) -> ScanUploadResponse:
    service = ScanSessionService(db)
    scan_session = service.get_for_user(scan_session_id, current_user)
    parsed_metadata = parse_metadata(metadata) if metadata else None
    normalized_pass = service.normalize_pass_type(pass_type)
    saved_session = service.save_pass_upload(
        scan_session=scan_session,
        pass_type=normalized_pass,
        file_name=video.filename,
        content_type=video.content_type,
        video_bytes=await video.read(),
        metadata=parsed_metadata,
    )
    return ScanUploadResponse(
        scanSession=scan_response(saved_session, service.get_model_asset_id(saved_session.id)),
        passType=normalized_pass,
        uploadedPasses=service.uploaded_passes(saved_session),
        requiredPasses=list(service.required_passes),
        readyForProcessing=service.is_ready_for_processing(saved_session),
        processingStarted=False,
        webDesignUrl=saved_session.web_design_url or service.web_design_url(saved_session.id),
    )


@router.get("/{scan_session_id}", response_model=ScanSessionResponse)
def get_scan_session(
    scan_session_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ScanSessionResponse:
    service = ScanSessionService(db)
    scan_session = service.get_for_user(scan_session_id, current_user)
    return scan_response(scan_session, service.get_model_asset_id(scan_session.id))


@router.get("/{scan_session_id}/status", response_model=ScanStatusResponse)
def get_scan_status(
    scan_session_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ScanStatusResponse:
    service = ScanSessionService(db)
    scan_session = service.get_for_user(scan_session_id, current_user)
    return status_response(scan_session, service)


@router.post("/{scan_session_id}/process", response_model=ScanStatusResponse)
def process_scan(
    scan_session_id: str,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ScanStatusResponse:
    service = ScanSessionService(db)
    scan_session = service.get_for_user(scan_session_id, current_user)
    if not service.is_ready_for_processing(scan_session):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload both required shoe videos before starting processing.",
        )
    if scan_session.status in ACTIVE_PROCESSING_STATUSES or scan_session.status == ScanStatus.COMPLETED:
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
