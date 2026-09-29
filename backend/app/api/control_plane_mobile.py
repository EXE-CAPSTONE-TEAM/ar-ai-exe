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


def get_client_ip(request: Request, trusted_proxies: list[str] | None = None) -> str:
    """
    Extract the real client IP address.

    Inspects X-Forwarded-For and X-Real-IP headers only when the direct peer IP
    is within the configured trusted_proxies list, preventing IP spoofing from untrusted clients.
    """
    peer_ip = request.client.host if request.client else "unknown"
    if trusted_proxies is None:
        try:
            trusted_proxies = get_settings().trusted_proxy_ips
        except Exception:
            trusted_proxies = ["127.0.0.1", "::1", "localhost"]

    if peer_ip in trusted_proxies or "*" in trusted_proxies:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
            if client_ip:
                return client_ip
        real_ip = request.headers.get("x-real-ip")
        if real_ip and real_ip.strip():
            return real_ip.strip()

    return peer_ip


def _enforce_exchange_rate_limit(client_ip: str) -> None:
    """
    In-process sliding-window rate limiter for compute grant exchange requests.

    Multi-Worker Topology:
    This rate limiter operates in-process per worker. In a multi-worker deployment
    (e.g., N Uvicorn/Gunicorn workers), the effective burst throughput per IP is up to
    (N * _EXCHANGE_RATE_LIMIT) req/min. To achieve global strict rate limiting across
    multiple workers/nodes:
      - Option B: Use a shared Redis store (sliding-window sorted set or INCR with TTL).
      - Option C: Enforce rate limiting at the ingress reverse proxy (e.g., Nginx limit_req
        or Cloudflare Rate Limiting Rules).

    Memory Management:
    Stale keys with no requests in the current window are evicted to ensure the table
    stays bounded over time.
    """
    now = time.monotonic()
    cutoff = now - _EXCHANGE_RATE_WINDOW

    # Bounded memory: evict stale keys whose most recent request is older than cutoff
    if len(_exchange_rate_history) > 100:
        stale_keys = [k for k, v in _exchange_rate_history.items() if not v or v[-1] <= cutoff]
        for k in stale_keys:
            _exchange_rate_history.pop(k, None)

    history = [t for t in _exchange_rate_history.get(client_ip, []) if t > cutoff]
    if len(history) >= _EXCHANGE_RATE_LIMIT:
        _exchange_rate_history[client_ip] = history
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
    client_ip = get_client_ip(request)
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
