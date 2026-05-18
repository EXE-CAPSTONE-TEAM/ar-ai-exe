import json
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import ModelAsset, User
from app.schemas.model_asset import ModelAssetResponse
from app.services.storage import get_storage_service


class ModelAssetService:
    def __init__(self, db: Session):
        self.db = db
        self.storage = get_storage_service()

    def get(self, model_asset_id: str) -> ModelAsset:
        asset = self.db.get(ModelAsset, model_asset_id)
        if not asset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model asset not found.")
        return asset

    def get_for_user(self, model_asset_id: str, user: User) -> ModelAsset:
        asset = self.get(model_asset_id)
        if asset.scan_session.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model asset not found.")
        return asset

    def file_key(self, asset: ModelAsset, file_type: str) -> str:
        key_by_type = {
            "glb": asset.glb_path,
            "obj": asset.obj_path,
            "mtl": asset.mtl_path,
            "texture": asset.texture_path,
            "quality-report": asset.quality_report_path,
        }
        if file_type not in key_by_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported model file type.",
            )
        key = key_by_type[file_type]
        if not self.storage.exists(key):
            legacy_path = Path(key)
            if not legacy_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"{file_type} file not found.",
                )
        return key

    def file_bytes(self, asset: ModelAsset, file_type: str) -> bytes:
        key = self.file_key(asset, file_type)
        if self.storage.exists(key):
            return self.storage.get_bytes(key)
        return Path(key).read_bytes()

    def response(self, asset: ModelAsset) -> ModelAssetResponse:
        quality_report: dict = {}
        try:
            quality_report = json.loads(self.file_bytes(asset, "quality-report").decode("utf-8"))
        except (HTTPException, json.JSONDecodeError, UnicodeDecodeError):
            quality_report = {}
        return ModelAssetResponse(
            id=asset.id,
            scanSessionId=asset.scan_session_id,
            glbUrl=f"/api/models/{asset.id}/download/glb",
            objUrl=f"/api/models/{asset.id}/download/obj",
            mtlUrl=f"/api/models/{asset.id}/download/mtl",
            textureUrl=f"/api/models/{asset.id}/download/texture",
            qualityReportUrl=f"/api/models/{asset.id}/quality-report",
            qualityReport=quality_report,
            createdAt=asset.created_at,
        )