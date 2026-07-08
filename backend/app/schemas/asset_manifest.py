from datetime import datetime

from pydantic import Field

from app.schemas.common import CamelModel


class AssetManifestFile(CamelModel):
    file_type: str = Field(alias="fileType")
    canonical_name: str = Field(alias="canonicalName")
    url: str
    content_type: str = Field(alias="contentType")
    size_bytes: int | None = Field(default=None, alias="sizeBytes")
    checksum: str | None = None


class AssetManifestVersion(CamelModel):
    asset_version_id: str = Field(alias="assetVersionId")
    asset_type: str = Field(alias="assetType")
    logical_key: str = Field(alias="logicalKey")
    version_number: int = Field(alias="versionNumber")
    status: str
    source_type: str = Field(alias="sourceType")
    legacy_model_asset_id: str | None = Field(default=None, alias="legacyModelAssetId")
    created_at: datetime = Field(alias="createdAt")
    files: list[AssetManifestFile]


class AssetManifestProject(CamelModel):
    id: str
    status: str
    updated_at: datetime = Field(alias="updatedAt")


class AssetManifestModelSection(CamelModel):
    latest_version: AssetManifestVersion | None = Field(default=None, alias="latestVersion")


class AssetManifestDesignSection(CamelModel):
    latest_revision: dict | None = Field(default=None, alias="latestRevision")


class AssetManifestPreviewSection(CamelModel):
    latest_version: AssetManifestVersion | None = Field(default=None, alias="latestVersion")


class AssetManifestExportsSection(CamelModel):
    latest_version: AssetManifestVersion | None = Field(default=None, alias="latestVersion")
    items: list[AssetManifestVersion] = Field(default_factory=list)


class ProjectAssetManifestResponse(CamelModel):
    manifest_version: int = Field(default=1, alias="manifestVersion")
    project: AssetManifestProject
    model: AssetManifestModelSection
    design: AssetManifestDesignSection
    preview: AssetManifestPreviewSection
    exports: AssetManifestExportsSection
