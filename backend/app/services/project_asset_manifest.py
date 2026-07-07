from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import AssetVersion, AssetVersionFile, AssetVersionType, Project, User
from app.schemas.asset_manifest import (
    AssetManifestDesignSection,
    AssetManifestExportsSection,
    AssetManifestFile,
    AssetManifestModelSection,
    AssetManifestPreviewSection,
    AssetManifestProject,
    AssetManifestVersion,
    ProjectAssetManifestResponse,
)
from app.services.asset_versions import AssetVersionService
from app.services.storage import get_storage_service


class ProjectAssetManifestService:
    def __init__(self, db: Session):
        self.db = db
        self.storage = get_storage_service()
        self.versions = AssetVersionService(db)

    def manifest_for_user(self, project_id: str, user: User) -> ProjectAssetManifestResponse:
        project = self._project_for_user(project_id, user)
        model = self.versions.latest_published(project.id, AssetVersionType.MODEL)
        preview = self.versions.latest_published(project.id, AssetVersionType.PREVIEW)
        exports = self.versions.list_published(project.id, AssetVersionType.EXPORT)
        return ProjectAssetManifestResponse(
            project=AssetManifestProject(
                id=project.id,
                status=project.status,
                updatedAt=project.updated_at,
            ),
            model=AssetManifestModelSection(
                latestVersion=self._version_response(project, model) if model else None
            ),
            design=AssetManifestDesignSection(latestRevision=None),
            preview=AssetManifestPreviewSection(
                latestVersion=self._version_response(project, preview) if preview else None
            ),
            exports=AssetManifestExportsSection(
                latestVersion=self._version_response(project, exports[0]) if exports else None,
                items=[self._version_response(project, version) for version in exports],
            ),
        )

    def file_for_user(
        self,
        project_id: str,
        asset_version_id: str,
        file_type: str,
        user: User,
    ) -> tuple[AssetVersionFile, bytes]:
        project = self._project_for_user(project_id, user)
        version = self.versions.get_for_project(project, asset_version_id)
        normalized_file_type = file_type.strip().lower()
        asset_file = next(
            (item for item in version.files if item.file_type == normalized_file_type),
            None,
        )
        if not asset_file or not self.storage.exists(asset_file.storage_key):
            raise ApiError(404, "ASSET_FILE_NOT_FOUND", "Asset version file not found.")
        return asset_file, self.storage.get_bytes(asset_file.storage_key)

    def _project_for_user(self, project_id: str, user: User) -> Project:
        project = self.db.get(Project, project_id)
        if not project or project.user_id != user.id:
            raise ApiError(404, "PROJECT_NOT_FOUND", "Project not found.")
        return project

    def _version_response(
        self,
        project: Project,
        version: AssetVersion,
    ) -> AssetManifestVersion:
        return AssetManifestVersion(
            assetVersionId=version.id,
            assetType=version.asset_type,
            logicalKey=version.logical_key,
            versionNumber=version.version_number,
            status=version.status,
            sourceType=version.source_type,
            legacyModelAssetId=AssetVersionService.legacy_id(version, "model_asset"),
            createdAt=version.created_at,
            files=[
                self._file_response(project, version, item)
                for item in sorted(version.files, key=lambda value: value.file_type)
            ],
        )

    def _file_response(
        self,
        project: Project,
        version: AssetVersion,
        asset_file: AssetVersionFile,
    ) -> AssetManifestFile:
        fallback_url = (
            f"/api/projects/{project.id}/asset-versions/{version.id}"
            f"/files/{asset_file.file_type}"
        )
        try:
            signed_url = self.storage.create_signed_url(asset_file.storage_key)
        except Exception:
            signed_url = None
        return AssetManifestFile(
            fileType=asset_file.file_type,
            canonicalName=asset_file.canonical_name,
            url=signed_url or fallback_url,
            contentType=asset_file.content_type,
            sizeBytes=asset_file.size_bytes,
            checksum=asset_file.checksum,
        )
