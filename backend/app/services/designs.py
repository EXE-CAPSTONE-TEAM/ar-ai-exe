import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Design, DesignPreviewStatus, DesignStatus, ModelAsset, User
from app.schemas.design import DesignConfig, DesignResponse
from app.services.decal_baker import DecalBakeService
from app.services.design_assets import DesignAssetService
from app.services.model_assets import ModelAssetService
from app.services.storage import get_storage_service


class DesignService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.storage = get_storage_service()

    def create(
        self,
        user: User,
        model_asset_id: str,
        name: str,
        config: DesignConfig | None,
    ) -> Design:
        asset = self.db.get(ModelAsset, model_asset_id)
        if not asset or asset.scan_session.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model asset not found.")

        config_payload = (
            config.model_dump(by_alias=True)
            if config
            else DesignConfig(modelAssetId=model_asset_id).model_dump(by_alias=True)
        )
        design = Design(
            user_id=user.id,
            model_asset_id=model_asset_id,
            name=name,
            design_config_path="",
            status=DesignStatus.DRAFT,
        )
        self.db.add(design)
        self.db.flush()

        config_object = self.storage.put_bytes(
            self._design_config_key(design.id),
            json.dumps(config_payload, indent=2).encode("utf-8"),
            "application/json",
        )
        design.design_config_path = config_object.key

        self.db.commit()
        self.db.refresh(design)
        self.refresh_preview(design)
        return design

    def get_for_user(self, design_id: str, user: User) -> Design:
        design = self.db.get(Design, design_id)
        if not design or design.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Design not found.")
        return design

    def update(
        self,
        design: Design,
        name: str | None = None,
        config: DesignConfig | None = None,
    ) -> Design:
        if name is not None:
            design.name = name
        if config is not None:
            self.storage.put_bytes(
                design.design_config_path,
                json.dumps(config.model_dump(by_alias=True), indent=2).encode("utf-8"),
                "application/json",
            )
        self.db.commit()
        self.db.refresh(design)
        if config is not None:
            self.refresh_preview(design)
        return design

    def response(self, design: Design) -> DesignResponse:
        return DesignResponse(
            id=design.id,
            userId=design.user_id,
            modelAssetId=design.model_asset_id,
            name=design.name,
            status=design.status,
            designConfig=self.read_config(design),
            previewGlbUrl=(
                f"/api/designs/{design.id}/preview/glb"
                if design.preview_status == DesignPreviewStatus.READY and design.preview_glb_path
                else None
            ),
            previewStatus=design.preview_status,
            previewErrorMessage=design.preview_error_message,
            createdAt=design.created_at,
            updatedAt=design.updated_at,
        )

    def read_config(self, design: Design) -> dict[str, Any]:
        if self.storage.exists(design.design_config_path):
            return json.loads(self.storage.get_bytes(design.design_config_path).decode("utf-8"))
        path = Path(design.design_config_path)
        return json.loads(path.read_text(encoding="utf-8"))

    def preview_glb_bytes(self, design: Design) -> bytes:
        if design.preview_status != DesignPreviewStatus.READY or not design.preview_glb_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Design preview GLB not found.",
            )
        if self.storage.exists(design.preview_glb_path):
            return self.storage.get_bytes(design.preview_glb_path)
        path = Path(design.preview_glb_path)
        if path.is_file():
            return path.read_bytes()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Design preview GLB not found.",
        )

    def refresh_preview(self, design: Design) -> None:
        design_config = self.read_config(design)
        if not self._has_decals(design_config):
            self._mark_preview_none(design)
            self.db.commit()
            self.db.refresh(design)
            return

        try:
            self._clear_preview_artifact(design)
            preview_dir = self._preview_folder(design.id)
            if preview_dir.exists():
                shutil.rmtree(preview_dir)
            preview_dir.mkdir(parents=True, exist_ok=True)

            asset = self.db.get(ModelAsset, design.model_asset_id)
            if not asset:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Model asset not found.",
                )

            source_glb = preview_dir / "source.glb"
            source_glb.write_bytes(ModelAssetService(self.db).file_bytes(asset, "glb"))
            asset_service = DesignAssetService(self.db)
            decals_baked = DecalBakeService(
                asset_resolver=lambda asset_id: asset_service.image_payload_for_user_id(
                    asset_id,
                    design.user_id,
                )
            ).bake(source_glb, preview_dir, design_config)
            if not decals_baked:
                self._mark_preview_none(design)
            else:
                baked_glb = preview_dir / "final_shoe.glb"
                preview_object = self.storage.put_bytes(
                    f"designs/{design.id}/preview/final_shoe.glb",
                    baked_glb.read_bytes(),
                    "model/gltf-binary",
                )
                design.preview_glb_path = preview_object.key
                design.preview_glb_size_bytes = preview_object.size_bytes
                design.preview_glb_content_type = preview_object.content_type
                design.preview_glb_checksum = preview_object.checksum
                design.preview_status = DesignPreviewStatus.READY
                design.preview_error_message = None
                design.preview_updated_at = datetime.utcnow()
        except Exception:
            self._mark_preview_failed(design)

        self.db.commit()
        self.db.refresh(design)

    def _design_config_key(self, design_id: str) -> str:
        return f"designs/{design_id}/design_config.json"

    def _preview_folder(self, design_id: str) -> Path:
        return self.settings.resolved_storage_root / "design_previews" / design_id

    def _has_decals(self, design_config: dict[str, Any]) -> bool:
        return bool(design_config.get("stickers")) or bool(design_config.get("texts"))

    def _clear_preview_artifact(self, design: Design) -> None:
        design.preview_glb_path = None
        design.preview_glb_size_bytes = None
        design.preview_glb_content_type = None
        design.preview_glb_checksum = None

    def _mark_preview_none(self, design: Design) -> None:
        self._clear_preview_artifact(design)
        design.preview_status = DesignPreviewStatus.NONE
        design.preview_error_message = None
        design.preview_updated_at = datetime.utcnow()

    def _mark_preview_failed(self, design: Design) -> None:
        self._clear_preview_artifact(design)
        design.preview_status = DesignPreviewStatus.FAILED
        design.preview_error_message = "Preview bake failed. The draft was saved and can be retried."
        design.preview_updated_at = datetime.utcnow()
