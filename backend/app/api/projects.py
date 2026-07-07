from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models import User
from app.schemas.design import DesignResponse
from app.schemas.asset_manifest import ProjectAssetManifestResponse
from app.schemas.project import (
    EditorContextResponse,
    ProjectCreate,
    ProjectDesignCreate,
    ProjectExportsResponse,
    ProjectListResponse,
    ProjectResponse,
)
from app.services.projects import ProjectService
from app.services.project_asset_manifest import ProjectAssetManifestService


router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ProjectResponse:
    service = ProjectService(db)
    return service.response(service.create(current_user, payload))


@router.get("", response_model=ProjectListResponse)
def list_projects(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ProjectListResponse:
    return ProjectService(db).list_for_user(current_user)


@router.get("/{project_id}/editor-context", response_model=EditorContextResponse)
def get_editor_context(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> EditorContextResponse:
    return ProjectService(db).editor_context(project_id, current_user)


@router.get("/{project_id}/asset-manifest", response_model=ProjectAssetManifestResponse)
def get_project_asset_manifest(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ProjectAssetManifestResponse:
    return ProjectAssetManifestService(db).manifest_for_user(project_id, current_user)


@router.get("/{project_id}/asset-versions/{asset_version_id}/files/{file_type}")
def download_project_asset_version_file(
    project_id: str,
    asset_version_id: str,
    file_type: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    asset_file, payload = ProjectAssetManifestService(db).file_for_user(
        project_id,
        asset_version_id,
        file_type,
        current_user,
    )
    return Response(
        content=payload,
        media_type=asset_file.content_type,
        headers={"Content-Disposition": f'inline; filename="{asset_file.canonical_name}"'},
    )


@router.post("/{project_id}/designs", response_model=DesignResponse, status_code=status.HTTP_201_CREATED)
def create_project_design(
    project_id: str,
    payload: ProjectDesignCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> DesignResponse:
    return ProjectService(db).create_design(project_id, current_user, payload)


@router.get("/{project_id}/exports", response_model=ProjectExportsResponse)
def list_project_exports(
    project_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ProjectExportsResponse:
    return ProjectService(db).exports(project_id, current_user)
