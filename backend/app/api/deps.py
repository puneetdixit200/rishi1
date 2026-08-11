from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.errors import raise_forbidden, raise_unauthorized
from app.core.security import (
    TokenError,
    decode_access_token,
    is_access_token_invalidated,
)
from app.db.session import get_db
from app.models import User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthContext:
    user: User
    token: str
    token_id: str
    token_expires_at_timestamp: int
    token_expires_at: datetime
    payload: dict[str, object]


@dataclass(frozen=True)
class BranchScope:
    all_branches: bool
    branch_ids: list[int]


def get_auth_context(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> AuthContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise_unauthorized()

    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except TokenError:
        raise_unauthorized("Invalid or expired access token.")

    token_id = str(payload["jti"])
    if is_access_token_invalidated(token_id):
        raise_unauthorized("Access token has been logged out.")

    try:
        user_id = int(str(payload["sub"]))
        expires_at_timestamp = int(payload["exp"])
    except (KeyError, TypeError, ValueError):
        raise_unauthorized("Invalid access token.")

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise_unauthorized("User account is inactive or no longer exists.")

    return AuthContext(
        user=user,
        token=token,
        token_id=token_id,
        token_expires_at_timestamp=expires_at_timestamp,
        token_expires_at=datetime.fromtimestamp(expires_at_timestamp, tz=UTC),
        payload=payload,
    )


def get_current_user(
    context: Annotated[AuthContext, Depends(get_auth_context)],
) -> User:
    return context.user


def require_roles(*allowed_roles: UserRole) -> Callable[[User], User]:
    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in allowed_roles:
            allowed = ", ".join(role.value for role in allowed_roles)
            raise_forbidden(f"Requires one of these roles: {allowed}.")
        return user

    return dependency


def require_admin(user: Annotated[User, Depends(require_roles(UserRole.ADMIN))]) -> User:
    return user


def require_operational_write_access(
    user: Annotated[
        User,
        Depends(require_roles(UserRole.ADMIN, UserRole.STORE_MANAGER, UserRole.STAFF)),
    ],
) -> User:
    return user


def require_reporting_access(
    user: Annotated[
        User,
        Depends(
            require_roles(
                UserRole.ADMIN,
                UserRole.STORE_MANAGER,
                UserRole.ANALYST,
            )
        ),
    ],
) -> User:
    return user


def get_branch_scope(user: Annotated[User, Depends(get_current_user)]) -> BranchScope:
    if user.role in {UserRole.ADMIN, UserRole.ANALYST}:
        return BranchScope(all_branches=True, branch_ids=[])

    if user.branch_id is None:
        raise_forbidden("This user does not have an assigned branch.")

    return BranchScope(all_branches=False, branch_ids=[user.branch_id])


def ensure_branch_access(user: User, branch_id: int) -> None:
    if user.role in {UserRole.ADMIN, UserRole.ANALYST}:
        return

    if user.branch_id != branch_id:
        raise_forbidden("You can only access data for your assigned branch.")
