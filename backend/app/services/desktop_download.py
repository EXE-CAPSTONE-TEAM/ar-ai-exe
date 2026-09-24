"""Save a presigned storage download straight into the user's Downloads folder.

KusShoes spec §E.5 / §G.2: exports reach up to 2 GiB, so the desktop editor hands the presigned
URL to the local sidecar instead of buffering the file in the webview. Only allowlisted storage
origins are fetched, the file name is reduced to a safe basename with a known extension, and the
body is streamed to a temp file under the destination before an atomic rename.
"""
from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Callable
from pathlib import Path

import httpx
from fastapi import HTTPException, status

from app.core.capability_urls import canonical_origin
from app.core.config import Settings, get_settings
from app.services.control_plane_bake import DOWNLOAD_CHUNK_BYTES, MEBIBYTE

# Export formats KusShoes produces (final_shoe.glb / final_shoe.obj.zip) plus the raw scan model.
ALLOWED_EXTENSIONS = {".glb", ".zip"}
# provenance: common filesystem NAME_MAX is 255 bytes; 180 leaves room for " (NN)" de-dup suffixes
# and matches KusShoes' own export filename cap (editor_service._safe_filename).
MAX_FILENAME_CHARS = 180
# provenance: bounded de-dup search — beyond this, collisions indicate a problem, not a user.
MAX_NAME_ATTEMPTS = 100
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(value: str) -> str:
    name = Path(value.replace("\\", "/")).name
    name = _UNSAFE.sub("_", name).strip("._")[:MAX_FILENAME_CHARS]
    suffix = Path(name).suffix.lower()
    if not name or suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Download file name must end in .glb or .zip.",
        )
    return name


def default_downloads_dir() -> Path:
    return Path.home() / "Downloads"


def _unique_destination(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    stem, suffix = candidate.stem, candidate.suffix
    for attempt in range(1, MAX_NAME_ATTEMPTS + 1):
        if not candidate.exists():
            return candidate
        candidate = directory / f"{stem} ({attempt}){suffix}"
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Too many files with this name in the Downloads folder.",
    )


class DesktopDownloadService:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        client_factory: Callable[[], httpx.AsyncClient] | None = None,
        downloads_dir: Path | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client_factory = client_factory or self._create_client
        self.downloads_dir = downloads_dir or self.settings.desktop_downloads_dir or default_downloads_dir()

    @property
    def _max_bytes(self) -> int:
        return max(1, self.settings.worker_max_output_size_mb) * MEBIBYTE

    def _create_client(self) -> httpx.AsyncClient:
        timeout_seconds = max(1, self.settings.worker_request_timeout_seconds)
        return httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 30)),
            follow_redirects=False,
            trust_env=False,
            headers={"Accept-Encoding": "identity"},
        )

    def _require_allowed_origin(self, url: str) -> None:
        if not self.settings.worker_allowed_storage_origins:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Worker storage origin allowlist is not configured.",
            )
        production = self.settings.environment.lower() in {"prod", "production"}
        try:
            allowed = {
                canonical_origin(origin, origin_only=True, require_https=production)
                for origin in self.settings.worker_allowed_storage_origins
            }
            origin = canonical_origin(url, origin_only=False, require_https=production)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Download URL is invalid.",
            ) from exc
        if origin not in allowed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Download origin is not allowed.",
            )

    async def download(self, *, url: str, filename: str) -> tuple[Path, int]:
        name = safe_filename(filename)
        self._require_allowed_origin(url)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)

        fd, raw_temp = tempfile.mkstemp(prefix=".kusshoes-", suffix=".part", dir=self.downloads_dir)
        temp_path = Path(raw_temp)
        total = 0
        try:
            with os.fdopen(fd, "wb") as stream:
                async with self.client_factory() as client, client.stream("GET", url) as response:
                    if response.status_code != status.HTTP_200_OK:
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=f"Storage download failed ({response.status_code}).",
                        )
                    declared = response.headers.get("content-length")
                    if declared and declared.isdigit() and int(declared) > self._max_bytes:
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail="Download exceeds the size limit.",
                        )
                    async for chunk in response.aiter_bytes(DOWNLOAD_CHUNK_BYTES):
                        total += len(chunk)
                        if total > self._max_bytes:
                            raise HTTPException(
                                status_code=status.HTTP_502_BAD_GATEWAY,
                                detail="Download exceeds the size limit.",
                            )
                        stream.write(chunk)
            if total == 0:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY, detail="Storage returned an empty file."
                )
            destination = _unique_destination(self.downloads_dir, name)
            os.replace(temp_path, destination)
            return destination, total
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail="Storage download failed."
            ) from exc
        finally:
            temp_path.unlink(missing_ok=True)
