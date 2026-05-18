from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.security import create_access_token
from app.db.database import get_db
from app.models import User
from app.schemas.auth import TokenResponse, UserCreate, UserLogin, UserResponse
from app.services.users import UserService


router = APIRouter(prefix="/auth", tags=["auth"])


def token_response(user: User) -> TokenResponse:
    token = create_access_token(user.id, {"role": user.role})
    return TokenResponse(accessToken=token, user=UserResponse.model_validate(user))


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    user = UserService(db).create_user(
        name=payload.name,
        email=str(payload.email),
        password=payload.password.get_secret_value(),
    )
    return token_response(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    user = UserService(db).authenticate(str(payload.email), payload.password.get_secret_value())
    return token_response(user)


@router.post("/demo-login", response_model=TokenResponse)
def demo_login(db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    if not get_settings().enable_demo_auth:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demo auth is disabled.")
    user = UserService(db).get_or_create_demo_user()
    return TokenResponse(accessToken=get_settings().demo_access_token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
def get_me(current_user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return UserResponse.model_validate(current_user)