"""Password hashing (bcrypt), JWT handling and the get_current_user dependency."""
from datetime import UTC, datetime, timedelta
from functools import cache

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import get_db
from app.models import User

BCRYPT_ROUNDS = 12

# auto_error=False so a missing header yields our 401 (not a framework-specific 403).
_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:  # e.g. password longer than bcrypt's 72-byte limit, or a malformed hash
        return False


@cache
def _dummy_hash() -> str:
    return hash_password("timing-equaliser")


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = db.scalar(select(User).options(joinedload(User.tenant)).where(User.username == username))
    if user is None:
        # Spend the same bcrypt time as a real check so response timing doesn't reveal valid usernames.
        verify_password(password, _dummy_hash())
        return None
    if not verify_password(password, user.password_hash) or not user.is_active:
        return None
    return user


def create_access_token(user: User) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "tenant_id": user.tenant_id,
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],  # pinned: never let the token choose its algorithm
        options={"require": ["sub", "exp"]},
    )


def _unauthorized(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Authenticate the request and return the user as stored in the DB.

    The token's tenant_id/role claims are informational only: every tenant check uses
    user.tenant_id loaded here, so a stale token (user moved tenant) can't widen access.
    """
    if credentials is None:
        raise _unauthorized("Not authenticated")
    try:
        user_id = int(decode_access_token(credentials.credentials)["sub"])
    except (jwt.PyJWTError, ValueError):
        raise _unauthorized() from None

    user = db.get(User, user_id, options=[joinedload(User.tenant)])
    if user is None or not user.is_active:
        raise _unauthorized()
    return user


def get_current_staff(user: User = Depends(get_current_user)) -> User:
    """Agency staff only. Case and scan data is tenant data, so tenant-less admins never reach it."""
    if user.role != "staff" or user.tenant_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only agency staff can access cases")
    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user
