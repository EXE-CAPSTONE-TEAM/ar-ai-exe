from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.models import User


class UserService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def create_user(self, name: str, email: str, password: str) -> User:
        normalized_email = email.strip().lower()
        existing = self.db.scalar(select(User).where(User.email == normalized_email))
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )

        user = User(
            role="user",
            name=name.strip(),
            email=normalized_email,
            password_hash=hash_password(password),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def authenticate(self, email: str, password: str) -> User:
        normalized_email = email.strip().lower()
        user = self.db.scalar(select(User).where(User.email == normalized_email))
        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )
        return user

    def get_by_id(self, user_id: str) -> User | None:
        return self.db.get(User, user_id)

    def get_or_create_demo_user(self) -> User:
        user = self.db.scalar(select(User).where(User.email == self.settings.demo_user_email))
        if user:
            return user

        user = User(
            role="demo_user",
            name="Demo User",
            email=self.settings.demo_user_email,
            password_hash=None,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user