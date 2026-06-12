from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.schemas.common import CamelModel


class MaterialConfig(CamelModel):
    roughness: float = 1.0
    metallic: float = 0.0


class DesignConfig(CamelModel):
    model_asset_id: str = Field(alias="modelAssetId")
    base_color: str = Field(default="#ffffff", alias="baseColor")
    material: MaterialConfig = Field(default_factory=MaterialConfig)
    stickers: list[dict[str, Any]] = Field(default_factory=list)
    texts: list[dict[str, Any]] = Field(default_factory=list)
    camera: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DesignCreate(CamelModel):
    model_asset_id: str = Field(alias="modelAssetId")
    name: str = Field(default="Untitled shoe design", min_length=1)
    config: DesignConfig | None = None


class DesignUpdate(CamelModel):
    name: str | None = Field(default=None, min_length=1)
    config: DesignConfig | None = None


class DesignResponse(CamelModel):
    id: str
    user_id: str = Field(alias="userId")
    project_id: str | None = Field(default=None, alias="projectId")
    model_asset_id: str = Field(alias="modelAssetId")
    name: str
    status: str
    design_config: dict[str, Any] = Field(alias="designConfig")
    preview_glb_url: str | None = Field(default=None, alias="previewGlbUrl")
    preview_status: Literal["none", "pending", "processing", "ready", "failed"] = Field(
        default="pending",
        alias="previewStatus",
    )
    preview_error_message: str | None = Field(default=None, alias="previewErrorMessage")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
