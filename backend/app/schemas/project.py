from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import CamelModel
from app.schemas.design import DesignResponse
from app.schemas.export import ExportPackageResponse


ProjectStatusValue = Literal["draft", "processing", "ready", "failed", "archived"]
ProjectSourceTypeValue = Literal["scan", "uploaded_glb", "uploaded_obj", "template"]
AssetStatusValue = Literal["uploaded", "processing", "ready", "failed"]


class ProjectCreate(CamelModel):
    name: str = Field(min_length=1, max_length=160)
    source_type: ProjectSourceTypeValue = Field(default="scan", alias="sourceType")
    template_id: str | None = Field(default=None, alias="templateId")


class ProjectResponse(CamelModel):
    id: str
    name: str
    status: ProjectStatusValue
    thumbnail_url: str | None = Field(default=None, alias="thumbnailUrl")
    source_type: ProjectSourceTypeValue = Field(alias="sourceType")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class ProjectListItem(CamelModel):
    id: str
    name: str
    status: ProjectStatusValue
    thumbnail_url: str | None = Field(default=None, alias="thumbnailUrl")
    updated_at: datetime = Field(alias="updatedAt")


class ProjectListResponse(CamelModel):
    items: list[ProjectListItem]


class EditorModelAsset(CamelModel):
    id: str
    project_id: str = Field(alias="projectId")
    status: AssetStatusValue
    source_type: ProjectSourceTypeValue = Field(alias="sourceType")
    canonical_glb_url: str | None = Field(default=None, alias="canonicalGlbUrl")
    obj_url: str | None = Field(default=None, alias="objUrl")
    mtl_url: str | None = Field(default=None, alias="mtlUrl")
    texture_urls: list[str] = Field(default_factory=list, alias="textureUrls")

    # Backward-compatible editor fields used by the existing React editor.
    scan_session_id: str | None = Field(default=None, alias="scanSessionId")
    glb_url: str | None = Field(default=None, alias="glbUrl")
    texture_url: str | None = Field(default=None, alias="textureUrl")
    metadata_url: str | None = Field(default=None, alias="metadataUrl")
    quality_report_url: str | None = Field(default=None, alias="qualityReportUrl")
    obj_package_zip_url: str | None = Field(default=None, alias="objPackageZipUrl")
    quality_report: dict = Field(default_factory=dict, alias="qualityReport")
    created_at: datetime | None = Field(default=None, alias="createdAt")


class EditorPermissions(CamelModel):
    can_edit: bool = Field(alias="canEdit")
    can_bake: bool = Field(alias="canBake")
    can_export: bool = Field(alias="canExport")


class EditorContextResponse(CamelModel):
    project: ProjectResponse
    model_asset: EditorModelAsset | None = Field(default=None, alias="modelAsset")
    latest_design: DesignResponse | None = Field(default=None, alias="latestDesign")
    permissions: EditorPermissions
    asset_manifest_url: str | None = Field(default=None, alias="assetManifestUrl")


class ProjectDesignCreate(CamelModel):
    design_config: dict = Field(alias="designConfig")
    name: str | None = Field(default=None, min_length=1, max_length=160)


class ProjectExportsResponse(CamelModel):
    items: list[ExportPackageResponse]
