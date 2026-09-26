import hashlib
import hmac
import re
import secrets
import threading
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.core.config import get_settings
from app.schemas.worker import (
    BakeWorkerRequest,
    BakeWorkerResponse,
    DesktopDownloadRequest,
    DesktopDownloadResponse,
    SidecarHandshakeResponse,
    PrepareWorkerRequest,
    PrepareWorkerResponse,
)
from app.services.control_plane_bake import ControlPlaneBakeService
from app.services.control_plane_prepare import ControlPlanePrepareService
from app.services.desktop_download import DesktopDownloadService


router = APIRouter(tags=["worker"])
_settings = get_settings()
_bake_slots = threading.BoundedSemaphore(value=max(1, _settings.worker_max_concurrent_bakes))


def require_control_plane_token(
    x_service_token: Annotated[
        str | None,
        Header(alias="X-Service-Token"),
    ] = None,
) -> None:
    expected = get_settings().control_plane_service_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Worker authentication is not configured.",
        )

    try:
        valid = bool(x_service_token) and secrets.compare_digest(
            x_service_token,
            expected,
        )
    except TypeError:
        valid = False
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid worker credentials.",
        )


@router.post(
    "/bake",
    response_model=BakeWorkerResponse,
    response_model_by_alias=False,
)
async def bake(
    payload: BakeWorkerRequest,
    _: Annotated[None, Depends(require_control_plane_token)],
) -> BakeWorkerResponse:
    if not _bake_slots.acquire(blocking=False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bake worker is at capacity.",
            headers={"Retry-After": "10"},
        )
    try:
        return await ControlPlaneBakeService().execute(payload)
    finally:
        _bake_slots.release()


@router.post(
    "/prepare",
    response_model=PrepareWorkerResponse,
    response_model_by_alias=False,
)
async def prepare(
    payload: PrepareWorkerRequest,
    _: Annotated[None, Depends(require_control_plane_token)],
) -> PrepareWorkerResponse:
    if not _bake_slots.acquire(blocking=False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Prepare worker is at capacity.",
            headers={"Retry-After": "10"},
        )
    try:
        return await ControlPlanePrepareService().execute(payload)
    finally:
        _bake_slots.release()



# provenance: 16–64 random bytes as hex; the desktop shell sends 32 bytes (spec §F.2).
_NONCE_PATTERN = re.compile(r"^[0-9a-f]{32,128}$")


@router.get("/handshake", response_model=SidecarHandshakeResponse)
async def handshake(nonce: Annotated[str, Query()]) -> SidecarHandshakeResponse:
    """Prove this sidecar holds the launch token without ever revealing it."""
    token = get_settings().control_plane_service_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Worker authentication is not configured.",
        )
    if not _NONCE_PATTERN.fullmatch(nonce):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Handshake nonce must be 32-128 lowercase hex characters.",
        )
    proof = hmac.new(token.encode("utf-8"), nonce.encode("ascii"), hashlib.sha256).hexdigest()
    return SidecarHandshakeResponse(proof=proof)


@router.post("/downloads", response_model=DesktopDownloadResponse)
async def save_download(
    payload: DesktopDownloadRequest,
    _: Annotated[None, Depends(require_control_plane_token)],
) -> DesktopDownloadResponse:
    path, size = await DesktopDownloadService().download(url=payload.url, filename=payload.filename)
    return DesktopDownloadResponse(path=str(path), file_size_bytes=size)
