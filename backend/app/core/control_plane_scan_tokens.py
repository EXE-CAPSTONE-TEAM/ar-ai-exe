from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.capability_urls import canonical_origin
from app.core.config import get_settings
from app.core.scan_identity import ControlPlaneScanPrincipal


CONTROL_PLANE_SCAN_TOKEN_TYPE = "control-plane-scan"
CONTROL_PLANE_SCAN_SCOPE = "scan:write"
OPAQUE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,256}$")


def create_control_plane_scan_token(principal: ControlPlaneScanPrincipal) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    lifetime_minutes = max(5, settings.control_plane_scan_token_minutes)
    payload = {
        "sub": principal.user_id,
        "project_id": principal.project_id,
        "completion_token": principal.completion_token,
        "project_name": principal.project_name,
        "web_project_url": principal.web_project_url,
        "scope": CONTROL_PLANE_SCAN_SCOPE,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=lifetime_minutes)).timestamp()),
        "jti": str(uuid.uuid4()),
        "typ": CONTROL_PLANE_SCAN_TOKEN_TYPE,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_control_plane_scan_token(token: str) -> ControlPlaneScanPrincipal:
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    return control_plane_scan_principal_from_claims(payload)


def control_plane_scan_principal_from_claims(
    payload: dict[str, Any],
) -> ControlPlaneScanPrincipal:
    if (
        payload.get("typ") != CONTROL_PLANE_SCAN_TOKEN_TYPE
        or payload.get("scope") != CONTROL_PLANE_SCAN_SCOPE
    ):
        raise jwt.InvalidTokenError("Invalid control-plane scan token type or scope.")

    user_id = _canonical_uuid(payload.get("sub"), "user")
    project_id = _canonical_uuid(payload.get("project_id"), "project")
    completion_token = payload.get("completion_token")
    project_name = payload.get("project_name")
    web_project_url = payload.get("web_project_url")

    if not isinstance(completion_token, str) or not OPAQUE_TOKEN_PATTERN.fullmatch(
        completion_token
    ):
        raise jwt.InvalidTokenError("Invalid control-plane completion capability.")
    if not isinstance(project_name, str):
        raise jwt.InvalidTokenError("Invalid control-plane project name.")
    project_name = project_name.strip()
    if not project_name or len(project_name) > 100:
        raise jwt.InvalidTokenError("Invalid control-plane project name.")
    if not isinstance(web_project_url, str):
        raise jwt.InvalidTokenError("Invalid control-plane project URL.")

    settings = get_settings()
    production = settings.environment.lower() in {"prod", "production"}
    try:
        canonical_origin(
            web_project_url,
            origin_only=False,
            require_https=production,
        )
    except ValueError as exc:
        raise jwt.InvalidTokenError("Invalid control-plane project URL.") from exc

    return ControlPlaneScanPrincipal(
        user_id=user_id,
        project_id=project_id,
        completion_token=completion_token,
        project_name=project_name,
        web_project_url=web_project_url,
    )


def _canonical_uuid(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise jwt.InvalidTokenError(f"Invalid control-plane {label} id.")
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError) as exc:
        raise jwt.InvalidTokenError(f"Invalid control-plane {label} id.") from exc
