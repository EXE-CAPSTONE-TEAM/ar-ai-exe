from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db.database import get_db
from app.models import User
from app.services.users import UserService


bearer_scheme = HTTPBearer(auto_error=False)

CSRF_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    settings = get_settings()
    token: str | None = None
    token_source = "bearer"
    if credentials is not None and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
    else:
        token = request.cookies.get(settings.auth_cookie_name)
        token_source = "cookie"

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing access token.",
        )

    if token_source == "cookie":
        _validate_csrf(request)

    if settings.enable_demo_auth and token == settings.demo_access_token:
        return UserService(db).get_or_create_demo_user()

    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired access token.",
        ) from exc

    user_id = payload.get("sub")
    if not isinstance(user_id, str):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid access token subject.",
        )

    user = UserService(db).get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    return user


def _validate_csrf(request: Request) -> None:
    if request.method.upper() not in CSRF_METHODS:
        return
    settings = get_settings()
    csrf_cookie = request.cookies.get(settings.csrf_cookie_name)
    csrf_header = request.headers.get(settings.csrf_header_name)
    if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing or invalid CSRF token.",
        )
