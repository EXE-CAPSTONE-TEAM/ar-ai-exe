from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.scan_sessions import scan_response
from app.db.database import get_db
from app.models import User
from app.schemas.model_asset import ModelAssetResponse, ModelImportResponse
from app.services.model_imports import ModelImportService, UploadedModelFile
from app.services.model_assets import ModelAssetService
from app.services.scan_metadata import parse_scan_metadata


router = APIRouter(prefix="/models", tags=["models"])


CONTENT_TYPE_BY_FILE_TYPE = {
    "glb": "model/gltf-binary",
    "obj": "text/plain",
    "mtl": "text/plain",
    "texture": "image/png",
    "metadata": "application/json",
    "quality-report": "application/json",
    "obj-package": "application/zip",
}

FILENAME_BY_FILE_TYPE = {
    "glb": "shoe_preview.glb",
    "obj": "shoe.obj",
    "mtl": "shoe.mtl",
    "texture": "shoe_texture.png",
    "metadata": "metadata.json",
    "quality-report": "quality_report.json",
    "obj-package": "shoe_obj_package.zip",
}


@router.get("/{model_asset_id}", response_model=ModelAssetResponse)
def get_model_asset(
    model_asset_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ModelAssetResponse:
    service = ModelAssetService(db)
    return service.response(service.get_for_user(model_asset_id, current_user))


@router.post("/import", response_model=ModelImportResponse, status_code=status.HTTP_201_CREATED)
async def import_model(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    name: Annotated[str, Form()],
    model_format: Annotated[str, Form(alias="format")],
    metadata: Annotated[str, Form()],
    model: Annotated[UploadFile | None, File()] = None,
    mtl: Annotated[UploadFile | None, File()] = None,
    texture: Annotated[UploadFile | None, File()] = None,
    package: Annotated[UploadFile | None, File()] = None,
    project_id: Annotated[str | None, Form(alias="projectId")] = None,
) -> ModelImportResponse:
    parsed_metadata = parse_scan_metadata(metadata)
    asset = ModelImportService(db).import_model(
        user=current_user,
        name=name,
        import_format=model_format,
        metadata=parsed_metadata,
        model_file=await uploaded_file(model),
        mtl_file=await uploaded_file(mtl),
        texture_file=await uploaded_file(texture),
        package_file=await uploaded_file(package),
        project_id=project_id,
    )
    model_service = ModelAssetService(db)
    return ModelImportResponse(
        scanSession=scan_response(asset.scan_session, asset.id),
        modelAsset=model_service.response(asset),
    )


@router.get("/{model_asset_id}/download/{file_type}")
def download_model_file(
    model_asset_id: str,
    file_type: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    service = ModelAssetService(db)
    asset = service.get_for_user(model_asset_id, current_user)
    payload = service.file_bytes(asset, file_type)
    media_type = CONTENT_TYPE_BY_FILE_TYPE.get(file_type, "application/octet-stream")
    filename = FILENAME_BY_FILE_TYPE.get(file_type, f"shoe_asset.{file_type}")
    return Response(
        content=payload,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{model_asset_id}/quality-report")
def get_quality_report(
    model_asset_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> JSONResponse:
    service = ModelAssetService(db)
    asset = service.get_for_user(model_asset_id, current_user)
    return JSONResponse(content=service.response(asset).quality_report)


async def uploaded_file(upload: UploadFile | None) -> UploadedModelFile | None:
    if not upload:
        return None
    return UploadedModelFile(
        file_name=upload.filename,
        content_type=upload.content_type,
        data=await upload.read(),
    )
