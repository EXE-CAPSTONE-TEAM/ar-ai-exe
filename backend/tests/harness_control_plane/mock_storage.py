"""Hermetic in-memory storage simulator for KusShoes control plane integration."""

from __future__ import annotations

import urllib.parse
from typing import Callable

import httpx


class MockHermeticStorage:
    """Simulates S3 / MinIO object storage with presigned download and upload URLs."""

    def __init__(self, base_origin: str = "https://storage.kusshoes.test") -> None:
        self.base_origin = base_origin.rstrip("/")
        self._stored_files: dict[str, tuple[str, bytes]] = {}  # path -> (content_type, bytes)
        self._uploaded_files: dict[str, tuple[str, bytes]] = {}  # path -> (content_type, bytes)

    def register_file(self, path: str, content: bytes, content_type: str = "application/octet-stream") -> str:
        """Register a file to be served on download and return its download URL."""
        normalized_path = "/" + path.lstrip("/")
        self._stored_files[normalized_path] = (content_type, content)
        return f"{self.base_origin}{normalized_path}?token=mock-presigned-download"

    def get_upload_url(self, path: str) -> str:
        """Generate a mock presigned upload URL for a given destination path."""
        normalized_path = "/" + path.lstrip("/")
        return f"{self.base_origin}{normalized_path}?token=mock-presigned-upload"

    def get_uploaded_data(self, path: str) -> bytes:
        """Retrieve uploaded file bytes by path."""
        normalized_path = "/" + path.lstrip("/")
        if normalized_path not in self._uploaded_files:
            raise KeyError(f"No file uploaded to '{normalized_path}'")
        return self._uploaded_files[normalized_path][1]

    def has_uploaded(self, path: str) -> bool:
        normalized_path = "/" + path.lstrip("/")
        return normalized_path in self._uploaded_files

    def create_transport(self) -> httpx.MockTransport:
        """Create an httpx MockTransport routing requests against this storage."""

        async def handler(request: httpx.Request) -> httpx.Response:
            parsed = urllib.parse.urlparse(str(request.url))
            path = parsed.path

            if request.method == "GET":
                if path in self._stored_files:
                    content_type, data = self._stored_files[path]
                    return httpx.Response(200, content=data, headers={"content-type": content_type})
                return httpx.Response(404, text=f"File not found: {path}")

            if request.method == "PUT":
                content_type = request.headers.get("content-type", "application/octet-stream")
                body = await request.aread()
                self._uploaded_files[path] = (content_type, body)
                return httpx.Response(200)

            return httpx.Response(405, text=f"Method {request.method} not allowed")

        return httpx.MockTransport(handler)

    def client_factory(self) -> Callable[[], httpx.AsyncClient]:
        transport = self.create_transport()
        return lambda: httpx.AsyncClient(transport=transport, follow_redirects=False)
