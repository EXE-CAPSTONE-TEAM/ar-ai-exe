from __future__ import annotations

import hashlib
import shutil
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

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

    def put_file(self, key: str, path: Path | str, content_type: str) -> StoredObject: ...

    def get_bytes(self, key: str) -> bytes: ...

    def iter_bytes(self, key: str, chunk_size: int = 1024 * 1024) -> Iterator[bytes]: ...

    def exists(self, key: str) -> bool: ...

    def create_signed_url(self, key: str, expires_in: int = 300) -> str | None: ...

    def create_upload_url(
        self, key: str, content_type: str = "video/mp4", expires_in: int = 900
    ) -> str: ...

    def head(self, key: str) -> dict[str, Any] | None: ...

    def delete(self, key: str) -> None: ...

    def download_to(self, key: str, path: Path | str, chunk_size: int = 1024 * 1024) -> Path: ...

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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Stored object not found."
            )
        return path.read_bytes()

    def iter_bytes(self, key: str, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
        path = self._resolve(key)
        if not path.exists() or not path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stored object not found.",
            )
        with path.open("rb") as stream:
            while chunk := stream.read(max(1, chunk_size)):
                yield chunk

    def exists(self, key: str) -> bool:
        return self._resolve(key).is_file()

    def put_file(self, key: str, path: Path | str, content_type: str) -> StoredObject:
        safe_key = normalize_key(key)
        target = self.root / safe_key
        target.parent.mkdir(parents=True, exist_ok=True)
        source = Path(path)
        shutil.copyfile(source, target)
        sha256 = hashlib.sha256()
        with source.open("rb") as f:
            while chunk := f.read(1024 * 1024):
                sha256.update(chunk)
        return StoredObject(
            key=safe_key,
            size_bytes=target.stat().st_size,
            content_type=content_type,
            checksum=sha256.hexdigest(),
        )

    def create_upload_url(
        self, key: str, content_type: str = "video/mp4", expires_in: int = 900
    ) -> str:
        safe_key = normalize_key(key)
        base = (
            self.settings.storage_public_base_url.rstrip("/")
            if self.settings.storage_public_base_url
            else "http://localhost/storage"
        )
        return f"{base}/{safe_key}"

    def head(self, key: str) -> dict[str, Any] | None:
        path = self._resolve(key)
        if not path.exists() or not path.is_file():
            return None
        size = path.stat().st_size
        return {
            "content_length": size,
            "ContentLength": size,
            "content_type": "video/mp4",
            "ContentType": "video/mp4",
            "etag": "",
            "ETag": "",
        }

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.exists() and path.is_file():
            path.unlink(missing_ok=True)

    def download_to(self, key: str, path: Path | str, chunk_size: int = 1024 * 1024) -> Path:
        target_path = Path(path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        source_path = self._resolve(key)
        if not source_path.exists() or not source_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Stored object not found."
            )
        with source_path.open("rb") as src, target_path.open("wb") as dst:
            while chunk := src.read(max(1, chunk_size)):
                dst.write(chunk)
        return target_path

    def create_signed_url(self, key: str, expires_in: int = 300) -> str | None:
        base = (
            self.settings.storage_public_base_url.rstrip("/")
            if self.settings.storage_public_base_url
            else "http://localhost/storage"
        )
        return f"{base}/{normalize_key(key)}"

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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Stored object not found."
            ) from exc
        return response["Body"].read()

    def iter_bytes(self, key: str, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
        safe_key = normalize_key(key)
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=safe_key)
        except Exception as exc:  # boto3 raises service-specific exceptions dynamically
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stored object not found.",
            ) from exc
        body = response["Body"]
        try:
            for chunk in body.iter_chunks(chunk_size=max(1, chunk_size)):
                if chunk:
                    yield chunk
        finally:
            body.close()

    def exists(self, key: str) -> bool:
        safe_key = normalize_key(key)
        try:
            self.client.head_object(Bucket=self.bucket, Key=safe_key)
            return True
        except Exception:
            return False

    def put_file(self, key: str, path: Path | str, content_type: str) -> StoredObject:
        safe_key = normalize_key(key)
        source = Path(path)
        sha256 = hashlib.sha256()
        with source.open("rb") as f:
            while chunk := f.read(1024 * 1024):
                sha256.update(chunk)
        checksum = sha256.hexdigest()
        size_bytes = source.stat().st_size
        self.client.upload_file(
            str(source),
            self.bucket,
            safe_key,
            ExtraArgs={
                "ContentType": content_type,
                "Metadata": {"sha256": checksum},
            },
        )
        return StoredObject(
            key=safe_key,
            size_bytes=size_bytes,
            content_type=content_type,
            checksum=checksum,
        )

    def create_upload_url(
        self, key: str, content_type: str = "video/mp4", expires_in: int = 900
    ) -> str:
        safe_key = normalize_key(key)
        return self.client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket,
                "Key": safe_key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in,
        )

    def head(self, key: str) -> dict[str, Any] | None:
        safe_key = normalize_key(key)
        try:
            response = self.client.head_object(Bucket=self.bucket, Key=safe_key)
            length = int(response["ContentLength"])
            content_type = str(response.get("ContentType") or "")
            etag = str(response.get("ETag") or "").strip('"')
            return {
                "content_length": length,
                "ContentLength": length,
                "content_type": content_type,
                "ContentType": content_type,
                "etag": etag,
                "ETag": etag,
            }
        except Exception:
            return None

    def delete(self, key: str) -> None:
        safe_key = normalize_key(key)
        try:
            self.client.delete_object(Bucket=self.bucket, Key=safe_key)
        except Exception:
            pass

    def download_to(self, key: str, path: Path | str, chunk_size: int = 1024 * 1024) -> Path:
        target_path = Path(path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        safe_key = normalize_key(key)
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=safe_key)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Stored object not found."
            ) from exc
        body = response["Body"]
        try:
            with target_path.open("wb") as stream:
                for chunk in body.iter_chunks(chunk_size=max(1, chunk_size)):
                    if chunk:
                        stream.write(chunk)
        finally:
            body.close()
        return target_path

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
