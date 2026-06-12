from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models import User
from app.schemas.design import DesignCreate, DesignResponse, DesignUpdate
from app.schemas.export import ExportPackageResponse
from app.schemas.job import JobResponse
from app.services.designs import DesignService
from app.services.export_packages import ExportPackageService
from app.services.jobs import JobService


router = APIRouter(prefix="/designs", tags=["designs"])


@router.post("", response_model=DesignResponse, status_code=status.HTTP_201_CREATED)
def create_design(
    payload: DesignCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> DesignResponse:
    service = DesignService(db)
    design = service.create(current_user, payload.model_asset_id, payload.name, payload.config)
    return service.response(design)


@router.get("/{design_id}", response_model=DesignResponse)
def get_design(
    design_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> DesignResponse:
    service = DesignService(db)
    return service.response(service.get_for_user(design_id, current_user))


@router.get("/{design_id}/preview/glb")
def get_design_preview_glb(
    design_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    service = DesignService(db)
    design = service.get_for_user(design_id, current_user)
    return Response(content=service.preview_glb_bytes(design), media_type="model/gltf-binary")


@router.put("/{design_id}", response_model=DesignResponse)
def update_design(
    design_id: str,
    payload: DesignUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> DesignResponse:
    service = DesignService(db)
    design = service.get_for_user(design_id, current_user)
    return service.response(service.update(design, payload.name, payload.config))


@router.post("/{design_id}/bake", response_model=JobResponse)
def bake_design(
    design_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> JobResponse:
    design_service = DesignService(db)
    design = design_service.get_for_user(design_id, current_user)
    job_service = JobService(db)
    return job_service.response(job_service.enqueue_bake(design, current_user))


@router.post("/{design_id}/export", response_model=ExportPackageResponse)
def export_design(
    design_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ExportPackageResponse:
    design_service = DesignService(db)
    design = design_service.get_for_user(design_id, current_user)
    export_service = ExportPackageService(db)
    return export_service.response(export_service.create(design))
