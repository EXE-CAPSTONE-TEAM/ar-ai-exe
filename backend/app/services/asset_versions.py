from __future__ import annotations

from dataclasses import dataclass
import re

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import (
    AssetVersion,
    AssetVersionFile,
    AssetVersionLegacyLink,
    AssetVersionStatus,
    Project,
    new_id,
)


PUBLISHED_ASSET_VERSION_STATUSES = {
    AssetVersionStatus.PUBLISHED,
    AssetVersionStatus.READY,
}
DEFAULT_LOGICAL_KEY = "primary"
MAX_STORAGE_KEY_LENGTH = 1024
ASSET_TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,119}$")


@dataclass(frozen=True)
class AssetVersionFileInput:
    file_type: str
    canonical_name: str
    storage_key: str
    content_type: str
    size_bytes: int | None
    checksum: str | None


class AssetVersionService:
    def __init__(self, db: Session):
        self.db = db

    def publish(
        self,
        *,
        project: Project,
        asset_type: str,
        logical_key: str = DEFAULT_LOGICAL_KEY,
        source_type: str,
        files: list[AssetVersionFileInput],
        status: str = AssetVersionStatus.READY,
        parent_asset_version_id: str | None = None,
        legacy_type: str | None = None,
        legacy_id: str | None = None,
        asset_version_id: str | None = None,
    ) -> AssetVersion:
        normalized_type = self._required_token(asset_type, "asset type")
        normalized_key = self._required_token(logical_key, "logical key")
        if status not in PUBLISHED_ASSET_VERSION_STATUSES:
            raise ApiError(400, "INVALID_ASSET_VERSION", "Published asset status is invalid.")
        if not files:
            raise ApiError(400, "INVALID_ASSET_VERSION", "An asset version requires files.")
        if len({item.file_type for item in files}) != len(files):
            raise ApiError(400, "INVALID_ASSET_VERSION", "Asset file types must be unique.")
        if bool(legacy_type) != bool(legacy_id):
            raise ApiError(
                400,
                "INVALID_ASSET_VERSION",
                "Legacy type and legacy ID must be provided together.",
            )
        if parent_asset_version_id:
            parent = self.db.get(AssetVersion, parent_asset_version_id)
            if not parent or parent.project_id != project.id:
                raise ApiError(400, "INVALID_ASSET_VERSION", "Parent asset version is invalid.")

        self._lock_project(project.id)

        version = AssetVersion(
            id=asset_version_id or new_id("assetv"),
            project_id=project.id,
            asset_type=normalized_type,
            logical_key=normalized_key,
            version_number=self.next_version_number(project.id, normalized_type, normalized_key),
            status=status,
            source_type=self._required_token(source_type, "source type"),
            parent_asset_version_id=parent_asset_version_id,
        )
        version.files = [
            AssetVersionFile(
                file_type=self._required_token(item.file_type, "file type"),
                canonical_name=self._canonical_name(item.canonical_name),
                storage_key=self._storage_key(item.storage_key),
                content_type=self._content_type(item.content_type),
                size_bytes=item.size_bytes,
                checksum=item.checksum,
            )
            for item in files
        ]
        if legacy_type and legacy_id:
            version.legacy_links = [
                AssetVersionLegacyLink(legacy_type=legacy_type, legacy_id=legacy_id)
            ]
        self.db.add(version)
        self.db.flush()
        return version

    def next_version_number(self, project_id: str, asset_type: str, logical_key: str) -> int:
        normalized_type = self._required_token(asset_type, "asset type")
        normalized_key = self._required_token(logical_key, "logical key")
        current = self.db.scalar(
            select(func.max(AssetVersion.version_number)).where(
                AssetVersion.project_id == project_id,
                AssetVersion.asset_type == normalized_type,
                AssetVersion.logical_key == normalized_key,
            )
        )
        return int(current or 0) + 1

    def _lock_project(self, project_id: str) -> None:
        locked_project_id = self.db.scalar(
            select(Project.id).where(Project.id == project_id).with_for_update()
        )
        if not locked_project_id:
            raise ApiError(404, "PROJECT_NOT_FOUND", "Project not found.")

    def latest_published(
        self,
        project_id: str,
        asset_type: str,
        logical_key: str = DEFAULT_LOGICAL_KEY,
    ) -> AssetVersion | None:
        normalized_type = self._required_token(asset_type, "asset type")
        normalized_key = self._required_token(logical_key, "logical key")
        return self.db.scalar(
            select(AssetVersion)
            .where(
                AssetVersion.project_id == project_id,
                AssetVersion.asset_type == normalized_type,
                AssetVersion.logical_key == normalized_key,
                AssetVersion.status.in_(PUBLISHED_ASSET_VERSION_STATUSES),
            )
            .order_by(desc(AssetVersion.version_number), desc(AssetVersion.id))
        )

    def get_for_project(self, project: Project, asset_version_id: str) -> AssetVersion:
        version = self.db.get(AssetVersion, asset_version_id)
        if not version or version.project_id != project.id:
            raise ApiError(404, "ASSET_VERSION_NOT_FOUND", "Asset version not found.")
        return version

    def list_published(
        self,
        project_id: str,
        asset_type: str,
        logical_key: str = DEFAULT_LOGICAL_KEY,
    ) -> list[AssetVersion]:
        normalized_type = self._required_token(asset_type, "asset type")
        normalized_key = self._required_token(logical_key, "logical key")
        return list(
            self.db.scalars(
                select(AssetVersion)
                .where(
                    AssetVersion.project_id == project_id,
                    AssetVersion.asset_type == normalized_type,
                    AssetVersion.logical_key == normalized_key,
                    AssetVersion.status.in_(PUBLISHED_ASSET_VERSION_STATUSES),
                )
                .order_by(desc(AssetVersion.version_number), desc(AssetVersion.id))
            ).all()
        )

    @staticmethod
    def legacy_id(version: AssetVersion, legacy_type: str) -> str | None:
        return next(
            (link.legacy_id for link in version.legacy_links if link.legacy_type == legacy_type),
            None,
        )

    @staticmethod
    def _required_token(value: str, label: str) -> str:
        normalized = value.strip().lower()
        if not ASSET_TOKEN_RE.fullmatch(normalized):
            raise ApiError(400, "INVALID_ASSET_VERSION", f"Invalid {label}.")
        return normalized

    @staticmethod
    def _canonical_name(value: str) -> str:
        normalized = value.strip()
        if (
            not normalized
            or len(normalized) > 180
            or "/" in normalized
            or "\\" in normalized
            or "\r" in normalized
            or "\n" in normalized
        ):
            raise ApiError(400, "INVALID_ASSET_VERSION", "Invalid canonical file name.")
        return normalized

    @staticmethod
    def _storage_key(value: str) -> str:
        normalized = value.strip()
        path_parts = normalized.split("/")
        if (
            not normalized
            or len(normalized) > MAX_STORAGE_KEY_LENGTH
            or "\r" in normalized
            or "\n" in normalized
            or "\\" in normalized
            or normalized.startswith("/")
            or any(part == ".." for part in path_parts)
        ):
            raise ApiError(400, "INVALID_ASSET_VERSION", "Invalid asset storage key.")
        return normalized

    @staticmethod
    def _content_type(value: str) -> str:
        normalized = value.strip()
        if (
            not normalized
            or len(normalized) > 120
            or "\r" in normalized
            or "\n" in normalized
        ):
            raise ApiError(400, "INVALID_ASSET_VERSION", "Invalid asset content type.")
        return normalized
