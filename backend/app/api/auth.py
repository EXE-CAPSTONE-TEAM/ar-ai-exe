import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.security import create_access_token
from app.db.database import get_db
from app.models import User
from app.schemas.auth import TokenResponse, UserCreate, UserLogin, UserResponse
from app.schemas.common import MessageResponse
from app.services.users import UserService


router = APIRouter(prefix="/auth", tags=["auth"])


def token_response(user: User, response: Response) -> TokenResponse:
    token = create_access_token(user.id, {"role": user.role})
    set_auth_cookies(response, token)
    return TokenResponse(accessToken=token, user=UserResponse.model_validate(user))


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: UserCreate,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    user = UserService(db).create_user(
        name=payload.name,
        email=str(payload.email),
        password=payload.password.get_secret_value(),
    )
    return token_response(user, response)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: UserLogin,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    user = UserService(db).authenticate(str(payload.email), payload.password.get_secret_value())
    return token_response(user, response)


@router.post("/demo-login", response_model=TokenResponse)
def demo_login(response: Response, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    if not get_settings().enable_demo_auth:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demo auth is disabled.")
    user = UserService(db).get_or_create_demo_user()
    set_auth_cookies(response, get_settings().demo_access_token)
    return TokenResponse(accessToken=get_settings().demo_access_token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
def get_me(current_user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.get("/token", response_model=TokenResponse)
def get_auth_token(
    current_user: Annotated[User, Depends(get_current_user)],
    response: Response,
) -> TokenResponse:
    token = create_access_token(current_user.id, {"role": current_user.role})
    set_auth_cookies(response, token)
    return TokenResponse(accessToken=token, user=UserResponse.model_validate(current_user))


@router.post("/logout", response_model=MessageResponse)
def logout(response: Response) -> MessageResponse:
    clear_auth_cookies(response)
    return MessageResponse(message="Logged out.")


def set_auth_cookies(response: Response, access_token: str) -> None:
    settings = get_settings()
    max_age = settings.jwt_access_token_minutes * 60
    cookie_domain = settings.auth_cookie_domain or None
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=access_token,
        max_age=max_age,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        domain=cookie_domain,
        path="/",
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=secrets.token_urlsafe(32),
        max_age=max_age,
        httponly=False,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        domain=cookie_domain,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    cookie_domain = settings.auth_cookie_domain or None
    response.delete_cookie(settings.auth_cookie_name, domain=cookie_domain, path="/")
    response.delete_cookie(settings.csrf_cookie_name, domain=cookie_domain, path="/")
