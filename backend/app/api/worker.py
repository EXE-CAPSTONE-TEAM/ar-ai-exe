import secrets
import threading
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.core.config import get_settings
from app.schemas.worker import BakeWorkerRequest, BakeWorkerResponse
from app.services.control_plane_bake import ControlPlaneBakeService


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
