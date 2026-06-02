from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import DesignAsset, User
from app.models.entities import new_id
from app.schemas.design_asset import DesignAssetResponse
from app.services.storage import get_storage_service


ALLOWED_DESIGN_ASSET_SOURCE_TYPES = {"upload", "canvas", "text-render"}
ALLOWED_DESIGN_ASSET_CONTENT_TYPES = {"image/png", "image/jpeg", "image/jpg"}
DESIGN_ASSET_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
}
MAX_DESIGN_ASSET_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True)
class UploadedDesignAsset:
    file_name: str | None
    content_type: str | None
    data: bytes


class DesignAssetService:
    def __init__(self, db: Session):
        self.db = db
        self.storage = get_storage_service()

    def create(self, user: User, upload: UploadedDesignAsset, source_type: str) -> DesignAsset:
        normalized_source = self._source_type(source_type)
        content_type = self._validate_upload(upload)
        extension = DESIGN_ASSET_EXTENSIONS[content_type]
        asset = DesignAsset(
            id=new_id("asset"),
            user_id=user.id,
            source_type=normalized_source,
            file_name=self._safe_file_name(upload.file_name, extension),
            storage_path="",
            content_type=content_type,
            size_bytes=0,
            checksum="",
        )
        self.db.add(asset)
        self.db.flush()

        stored = self.storage.put_bytes(
            f"design-assets/{user.id}/{asset.id}{extension}",
            upload.data,
            content_type,
        )
        asset.storage_path = stored.key
        asset.size_bytes = stored.size_bytes
        asset.checksum = stored.checksum
        asset.content_type = stored.content_type
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def get(self, asset_id: str) -> DesignAsset:
        asset = self.db.get(DesignAsset, asset_id)
        if not asset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Design asset not found.")
        return asset

    def get_for_user(self, asset_id: str, user: User) -> DesignAsset:
        asset = self.get(asset_id)
        if asset.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Design asset not found.")
        return asset

    def get_for_user_id(self, asset_id: str, user_id: str) -> DesignAsset:
        asset = self.get(asset_id)
        if asset.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Design asset not found.")
        return asset

    def file_bytes(self, asset: DesignAsset) -> bytes:
        if self.storage.exists(asset.storage_path):
            return self.storage.get_bytes(asset.storage_path)
        path = Path(asset.storage_path)
        if path.is_file():
            return path.read_bytes()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Design asset file not found.")

    def image_payload_for_user_id(self, asset_id: str, user_id: str) -> tuple[bytes, str]:
        asset = self.get_for_user_id(asset_id, user_id)
        return self.file_bytes(asset), asset.content_type

    def response(self, asset: DesignAsset) -> DesignAssetResponse:
        return DesignAssetResponse(
            id=asset.id,
            sourceType=asset.source_type,
            fileName=asset.file_name,
            contentType=asset.content_type,
            sizeBytes=asset.size_bytes,
            checksum=asset.checksum,
            downloadUrl=f"/api/design-assets/{asset.id}/download",
            createdAt=asset.created_at,
        )

    def _source_type(self, source_type: str) -> str:
        normalized = source_type.strip().lower()
        if normalized not in ALLOWED_DESIGN_ASSET_SOURCE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Design asset sourceType must be upload, canvas, or text-render.",
            )
        return normalized

    def _validate_upload(self, upload: UploadedDesignAsset) -> str:
        if not upload.data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Design asset image is empty.")
        if len(upload.data) > MAX_DESIGN_ASSET_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Design asset image exceeds the 5 MB upload limit.",
            )

        content_type = (upload.content_type or "").split(";", 1)[0].strip().lower()
        if content_type not in ALLOWED_DESIGN_ASSET_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Design asset must be a PNG or JPEG image.",
            )

        detected = self._detect_content_type(upload.data)
        if detected != self._normalize_content_type(content_type):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Design asset image content does not match its declared type.",
            )
        return detected

    def _detect_content_type(self, data: bytes) -> str:
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if data.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Design asset must contain valid PNG or JPEG bytes.",
        )

    def _normalize_content_type(self, content_type: str) -> str:
        return "image/jpeg" if content_type == "image/jpg" else content_type

    def _safe_file_name(self, file_name: str | None, extension: str) -> str:
        stem = Path(file_name or "artwork").stem
        cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._")[:120] or "artwork"
        return f"{cleaned}{extension}"
