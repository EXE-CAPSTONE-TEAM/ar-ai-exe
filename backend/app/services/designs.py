import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Design, DesignStatus, ModelAsset, User
from app.schemas.design import DesignConfig, DesignResponse
from app.services.storage import get_storage_service


class DesignService:
    def __init__(self, db: Session):
        self.db = db
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
        return design

    def response(self, design: Design) -> DesignResponse:
        return DesignResponse(
            id=design.id,
            userId=design.user_id,
            modelAssetId=design.model_asset_id,
            name=design.name,
            status=design.status,
            designConfig=self.read_config(design),
            createdAt=design.created_at,
            updatedAt=design.updated_at,
        )

    def read_config(self, design: Design) -> dict[str, Any]:
        if self.storage.exists(design.design_config_path):
            return json.loads(self.storage.get_bytes(design.design_config_path).decode("utf-8"))
        path = Path(design.design_config_path)
        return json.loads(path.read_text(encoding="utf-8"))

    def _design_config_key(self, design_id: str) -> str:
        return f"designs/{design_id}/design_config.json"