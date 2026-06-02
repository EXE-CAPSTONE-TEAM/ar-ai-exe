from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models import User
from app.schemas.design_asset import DesignAssetResponse
from app.services.design_assets import (
    DesignAssetService,
    MAX_DESIGN_ASSET_BYTES,
    UploadedDesignAsset,
)


router = APIRouter(prefix="/design-assets", tags=["design-assets"])


@router.post("", response_model=DesignAssetResponse, status_code=status.HTTP_201_CREATED)
async def create_design_asset(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File()],
    source_type: Annotated[str, Form(alias="sourceType")],
) -> DesignAssetResponse:
    service = DesignAssetService(db)
    asset = service.create(
        current_user,
        UploadedDesignAsset(
            file_name=file.filename,
            content_type=file.content_type,
            data=await file.read(MAX_DESIGN_ASSET_BYTES + 1),
        ),
        source_type,
    )
    return service.response(asset)


@router.get("/{asset_id}/download")
def download_design_asset(
    asset_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    service = DesignAssetService(db)
    asset = service.get_for_user(asset_id, current_user)
    return Response(
        content=service.file_bytes(asset),
        media_type=asset.content_type,
        headers={"Content-Disposition": f'inline; filename="{asset.file_name}"'},
    )
