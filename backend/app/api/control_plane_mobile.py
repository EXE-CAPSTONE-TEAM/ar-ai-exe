import time
from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.config import get_settings
from app.core.control_plane_scan_tokens import create_control_plane_scan_token
from app.core.scan_identity import ControlPlaneScanPrincipal
from app.schemas.control_plane_mobile import (
    ComputeGrantExchangeRequest,
    ComputeGrantExchangeResponse,
)
from app.services.control_plane_mobile import (
    ControlPlaneGrantRejected,
    ControlPlaneMobileClient,
    ControlPlaneMobileError,
)

router = APIRouter(prefix="/control-plane", tags=["control-plane-mobile"])

_exchange_rate_history: dict[str, list[float]] = defaultdict(list)
_EXCHANGE_RATE_LIMIT = 10  # provenance: mobile grant exchange burst limit
_EXCHANGE_RATE_WINDOW = 60.0  # provenance: 60-second sliding rate limit window


def _enforce_exchange_rate_limit(client_ip: str) -> None:
    now = time.monotonic()
    cutoff = now - _EXCHANGE_RATE_WINDOW
    history = [t for t in _exchange_rate_history[client_ip] if t > cutoff]
    if len(history) >= _EXCHANGE_RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many compute grant exchange requests. Please try again later.",
        )
    history.append(now)
    _exchange_rate_history[client_ip] = history


def get_control_plane_mobile_client() -> ControlPlaneMobileClient:
    return ControlPlaneMobileClient()


@router.post("/scan/exchange", response_model=ComputeGrantExchangeResponse)
def exchange_scan_grant(
    payload: ComputeGrantExchangeRequest,
    request: Request,
    client: Annotated[ControlPlaneMobileClient, Depends(get_control_plane_mobile_client)],
) -> ComputeGrantExchangeResponse:
    client_ip = request.client.host if request.client else "unknown"
    _enforce_exchange_rate_limit(client_ip)
    try:
        claim = client.claim_compute_grant(payload.compute_grant)
    except ControlPlaneGrantRejected as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compute grant is invalid or expired.",
        ) from exc
    except ControlPlaneMobileError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The KusShoes control plane is temporarily unavailable.",
        ) from exc

    principal = ControlPlaneScanPrincipal(
        user_id=str(claim.user_id),
        project_id=str(claim.project_id),
        completion_token=claim.completion_token,
        project_name=claim.project_name,
        web_project_url=claim.web_project_url,
    )
    settings = get_settings()
    return ComputeGrantExchangeResponse(
        accessToken=create_control_plane_scan_token(principal),
        tokenType="bearer",
        expiresIn=max(5, settings.control_plane_scan_token_minutes) * 60,
        projectId=claim.project_id,
        projectName=claim.project_name,
        webProjectUrl=claim.web_project_url,
    )
