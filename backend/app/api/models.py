from typing import Annotated

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models import User
from app.schemas.model_asset import ModelAssetResponse
from app.services.model_assets import ModelAssetService


router = APIRouter(prefix="/models", tags=["models"])


CONTENT_TYPE_BY_FILE_TYPE = {
    "glb": "model/gltf-binary",
    "obj": "text/plain",
    "mtl": "text/plain",
    "texture": "image/png",
}


@router.get("/{model_asset_id}", response_model=ModelAssetResponse)
def get_model_asset(
    model_asset_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ModelAssetResponse:
    service = ModelAssetService(db)
    return service.response(service.get_for_user(model_asset_id, current_user))


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
    filename = f"shoe_base.{file_type if file_type != 'texture' else 'png'}"
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