import json
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import AssetStatus, ModelAsset, ProjectStatus, ScanSession, User
from app.schemas.model_asset import ModelAssetResponse
from app.services.storage import get_storage_service


@dataclass(frozen=True)
class ModelAssetFiles:
    glb: Path
    obj: Path
    mtl: Path
    texture: Path
    metadata: Path
    quality_report: Path
    obj_package_zip: Path


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
            "metadata": asset.metadata_path,
            "quality-report": asset.quality_report_path,
            "obj-package": asset.obj_package_zip_path,
        }
        if file_type not in key_by_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported model file type.",
            )
        key = key_by_type[file_type]
        if not key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{file_type} file not found.",
            )
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

    def create_from_files(
        self,
        scan_session_id: str,
        files: ModelAssetFiles,
        storage_prefix: str | None = None,
        source_type: str = "scan",
    ) -> ModelAsset:
        prefix = (storage_prefix or f"models/{scan_session_id}").strip("/")
        glb_object = self.storage.put_bytes(
            f"{prefix}/shoe_preview.glb",
            files.glb.read_bytes(),
            "model/gltf-binary",
        )
        obj_object = self.storage.put_bytes(
            f"{prefix}/shoe.obj",
            files.obj.read_bytes(),
            "text/plain",
        )
        mtl_object = self.storage.put_bytes(
            f"{prefix}/shoe.mtl",
            files.mtl.read_bytes(),
            "text/plain",
        )
        texture_object = self.storage.put_bytes(
            f"{prefix}/shoe_texture.png",
            files.texture.read_bytes(),
            "image/png",
        )
        metadata_object = self.storage.put_bytes(
            f"{prefix}/metadata.json",
            files.metadata.read_bytes(),
            "application/json",
        )
        quality_object = self.storage.put_bytes(
            f"{prefix}/quality_report.json",
            files.quality_report.read_bytes(),
            "application/json",
        )
        obj_package_object = self.storage.put_bytes(
            f"{prefix}/shoe_obj_package.zip",
            files.obj_package_zip.read_bytes(),
            "application/zip",
        )

        asset = ModelAsset(
            scan_session_id=scan_session_id,
            status=AssetStatus.READY,
            source_type=source_type,
            glb_path=glb_object.key,
            glb_size_bytes=glb_object.size_bytes,
            glb_content_type=glb_object.content_type,
            glb_checksum=glb_object.checksum,
            obj_path=obj_object.key,
            obj_size_bytes=obj_object.size_bytes,
            obj_content_type=obj_object.content_type,
            obj_checksum=obj_object.checksum,
            mtl_path=mtl_object.key,
            mtl_size_bytes=mtl_object.size_bytes,
            mtl_content_type=mtl_object.content_type,
            mtl_checksum=mtl_object.checksum,
            texture_path=texture_object.key,
            texture_size_bytes=texture_object.size_bytes,
            texture_content_type=texture_object.content_type,
            texture_checksum=texture_object.checksum,
            metadata_path=metadata_object.key,
            metadata_size_bytes=metadata_object.size_bytes,
            metadata_content_type=metadata_object.content_type,
            metadata_checksum=metadata_object.checksum,
            quality_report_path=quality_object.key,
            quality_report_size_bytes=quality_object.size_bytes,
            quality_report_content_type=quality_object.content_type,
            quality_report_checksum=quality_object.checksum,
            obj_package_zip_path=obj_package_object.key,
            obj_package_zip_size_bytes=obj_package_object.size_bytes,
            obj_package_zip_content_type=obj_package_object.content_type,
            obj_package_zip_checksum=obj_package_object.checksum,
        )
        self.db.add(asset)
        scan_session = self.db.get(ScanSession, scan_session_id)
        if scan_session and scan_session.project:
            scan_session.project.status = ProjectStatus.READY
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def response(self, asset: ModelAsset) -> ModelAssetResponse:
        quality_report: dict = {}
        try:
            quality_report = json.loads(self.file_bytes(asset, "quality-report").decode("utf-8"))
        except (HTTPException, json.JSONDecodeError, UnicodeDecodeError):
            quality_report = {}
        return ModelAssetResponse(
            id=asset.id,
            scanSessionId=asset.scan_session_id,
            projectId=asset.scan_session.project_id if asset.scan_session else None,
            status=asset.status,
            sourceType=asset.source_type,
            glbUrl=f"/api/models/{asset.id}/download/glb",
            canonicalGlbUrl=f"/api/models/{asset.id}/download/glb",
            objUrl=f"/api/models/{asset.id}/download/obj",
            mtlUrl=f"/api/models/{asset.id}/download/mtl",
            textureUrl=f"/api/models/{asset.id}/download/texture",
            textureUrls=[f"/api/models/{asset.id}/download/texture"],
            metadataUrl=f"/api/models/{asset.id}/download/metadata",
            qualityReportUrl=f"/api/models/{asset.id}/quality-report",
            objPackageZipUrl=f"/api/models/{asset.id}/download/obj-package",
            qualityReport=quality_report,
            createdAt=asset.created_at,
        )
