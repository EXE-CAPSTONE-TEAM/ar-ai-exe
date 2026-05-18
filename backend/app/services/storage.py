from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from fastapi import HTTPException, status

from app.core.config import get_settings


@dataclass(frozen=True)
class StoredObject:
    key: str
    size_bytes: int
    content_type: str
    checksum: str


class StorageService(Protocol):
    def put_bytes(self, key: str, data: bytes, content_type: str) -> StoredObject: ...

    def get_bytes(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...

    def create_signed_url(self, key: str, expires_in: int = 300) -> str | None: ...

    def local_path(self, key: str) -> Path | None: ...


def checksum_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_key(key: str) -> str:
    normalized = key.replace("\\", "/").lstrip("/")
    if not normalized or ".." in Path(normalized).parts:
        raise ValueError("Invalid storage key.")
    return normalized


class LocalStorageService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.root = self.settings.resolved_storage_root

    def put_bytes(self, key: str, data: bytes, content_type: str) -> StoredObject:
        safe_key = normalize_key(key)
        path = self.root / safe_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StoredObject(
            key=safe_key,
            size_bytes=len(data),
            content_type=content_type,
            checksum=checksum_bytes(data),
        )

    def get_bytes(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.exists() or not path.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored object not found.")
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        return self._resolve(key).is_file()

    def create_signed_url(self, key: str, expires_in: int = 300) -> str | None:
        if not self.settings.storage_public_base_url:
            return None
        return f"{self.settings.storage_public_base_url.rstrip('/')}/{normalize_key(key)}"

    def local_path(self, key: str) -> Path | None:
        return self._resolve(key)

    def _resolve(self, key: str) -> Path:
        safe_key = normalize_key(key)
        path = (self.root / safe_key).resolve()
        root = self.root.resolve()
        if root not in path.parents and path != root:
            raise ValueError("Storage key escapes storage root.")
        return path


class S3StorageService:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.s3_bucket_name:
            raise RuntimeError("S3_BUCKET_NAME is required when STORAGE_BACKEND=s3.")
        import boto3

        self.bucket = settings.s3_bucket_name
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url or None,
            region_name=settings.s3_region_name or None,
            aws_access_key_id=settings.s3_access_key_id or None,
            aws_secret_access_key=settings.s3_secret_access_key or None,
        )

    def put_bytes(self, key: str, data: bytes, content_type: str) -> StoredObject:
        safe_key = normalize_key(key)
        self.client.put_object(
            Bucket=self.bucket,
            Key=safe_key,
            Body=data,
            ContentType=content_type,
            Metadata={"sha256": checksum_bytes(data)},
        )
        return StoredObject(
            key=safe_key,
            size_bytes=len(data),
            content_type=content_type,
            checksum=checksum_bytes(data),
        )

    def get_bytes(self, key: str) -> bytes:
        safe_key = normalize_key(key)
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=safe_key)
        except Exception as exc:  # boto3 raises service-specific exceptions dynamically
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored object not found.") from exc
        return response["Body"].read()

    def exists(self, key: str) -> bool:
        safe_key = normalize_key(key)
        try:
            self.client.head_object(Bucket=self.bucket, Key=safe_key)
            return True
        except Exception:
            return False

    def create_signed_url(self, key: str, expires_in: int = 300) -> str | None:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": normalize_key(key)},
            ExpiresIn=expires_in,
        )

    def local_path(self, key: str) -> Path | None:
        return None


def get_storage_service() -> StorageService:
    backend = get_settings().storage_backend.lower()
    if backend == "s3":
        return S3StorageService()
    if backend == "local":
        return LocalStorageService()
    raise RuntimeError(f"Unsupported storage backend: {backend}")