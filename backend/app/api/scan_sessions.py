import json
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.database import get_db
from app.models import ScanSession, User
from app.schemas.scan import (
    ScanMetadata,
    ScanSessionCreate,
    ScanSessionResponse,
    ScanStatusResponse,
    ScanUploadResponse,
)
from app.services.scan_sessions import ScanSessionService
from app.workers.reconstruction_worker import process_scan_session


router = APIRouter(prefix="/scan-sessions", tags=["scan-sessions"])


def scan_response(scan_session: ScanSession, model_asset_id: str | None) -> ScanSessionResponse:
    payload = ScanSessionResponse.model_validate(scan_session).model_dump()
    payload["model_asset_id"] = model_asset_id
    if not payload.get("web_design_url"):
        payload["web_design_url"] = f"{get_settings().web_app_base_url.rstrip('/')}/design?scanId={scan_session.id}"
    return ScanSessionResponse.model_validate(payload)


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
    background_tasks.add_task(process_scan_session, saved_session.id)
    return ScanUploadResponse(
        scanSession=scan_response(saved_session, service.get_model_asset_id(saved_session.id)),
        processingStarted=True,
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
    return ScanStatusResponse(
        id=scan_session.id,
        status=scan_session.status,
        errorMessage=scan_session.error_message,
        modelAssetId=service.get_model_asset_id(scan_session.id),
        updatedAt=scan_session.updated_at,
    )


@router.post("/{scan_session_id}/process", response_model=ScanStatusResponse)
def process_scan(
    scan_session_id: str,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ScanStatusResponse:
    service = ScanSessionService(db)
    scan_session = service.get_for_user(scan_session_id, current_user)
    if not scan_session.raw_video_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload a video before starting processing.",
        )
    background_tasks.add_task(process_scan_session, scan_session.id)
    return ScanStatusResponse(
        id=scan_session.id,
        status=scan_session.status,
        errorMessage=scan_session.error_message,
        modelAssetId=service.get_model_asset_id(scan_session.id),
        updatedAt=scan_session.updated_at,
    )


def parse_metadata(raw_metadata: str) -> ScanMetadata:
    try:
        payload = json.loads(raw_metadata)
        return ScanMetadata.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid scan metadata: {exc}",
        ) from exc
