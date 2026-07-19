from typing import Annotated, TypeAlias

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.api.deps import bearer_scheme, get_current_user
from app.core.control_plane_scan_tokens import (
    CONTROL_PLANE_SCAN_TOKEN_TYPE,
    control_plane_scan_principal_from_claims,
)
from app.core.scan_identity import ControlPlaneScanPrincipal
from app.core.security import decode_access_token
from app.db.database import get_db
from app.models import User


ScanActor: TypeAlias = User | ControlPlaneScanPrincipal


def get_scan_actor(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> ScanActor:
    """Accept legacy users or a bearer-only, project-scoped control-plane scan token."""

    if credentials is None or credentials.scheme.lower() != "bearer":
        return get_current_user(request, credentials, db)

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired access token.",
        ) from exc

    if payload.get("typ") != CONTROL_PLANE_SCAN_TOKEN_TYPE:
        return get_current_user(request, credentials, db)

    try:
        return control_plane_scan_principal_from_claims(payload)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired scan token.",
        ) from exc
