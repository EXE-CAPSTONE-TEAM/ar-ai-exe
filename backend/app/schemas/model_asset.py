from datetime import datetime

from pydantic import Field

from app.schemas.common import CamelModel
from app.schemas.scan import ScanSessionResponse


class ModelAssetResponse(CamelModel):
    id: str
    scan_session_id: str = Field(alias="scanSessionId")
    project_id: str | None = Field(default=None, alias="projectId")
    status: str = "ready"
    source_type: str = Field(default="scan", alias="sourceType")
    glb_url: str = Field(alias="glbUrl")
    canonical_glb_url: str = Field(alias="canonicalGlbUrl")
    obj_url: str = Field(alias="objUrl")
    mtl_url: str = Field(alias="mtlUrl")
    texture_url: str = Field(alias="textureUrl")
    texture_urls: list[str] = Field(default_factory=list, alias="textureUrls")
    metadata_url: str = Field(alias="metadataUrl")
    quality_report_url: str = Field(alias="qualityReportUrl")
    obj_package_zip_url: str = Field(alias="objPackageZipUrl")
    quality_report: dict = Field(default_factory=dict, alias="qualityReport")
    created_at: datetime = Field(alias="createdAt")


class ModelImportResponse(CamelModel):
    scan_session: ScanSessionResponse = Field(alias="scanSession")
    model_asset: ModelAssetResponse = Field(alias="modelAsset")
