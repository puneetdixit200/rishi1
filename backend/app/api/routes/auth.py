from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    AuthContext,
    BranchScope,
    get_auth_context,
    get_branch_scope,
    get_current_user,
    require_admin,
)
from app.api.errors import raise_unauthorized
from app.core.security import (
    create_access_token,
    invalidate_access_token,
    verify_password,
)
from app.db.session import get_db
from app.models import User
from app.schemas.auth import (
    BranchScopeResponse,
    LoginRequest,
    MessageResponse,
    TokenResponse,
    UserRead,
)
from app.services.audit import write_audit_log

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: LoginRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == credentials.email))
    if user is None or not verify_password(credentials.password, user.password_hash):
        write_audit_log(
            db,
            action="auth.login_failure",
            entity_type="user",
            new_value_json={"email": credentials.email, "success": False},
            request=request,
            notes="Invalid email or password.",
            commit=True,
        )
        raise_unauthorized("Invalid email or password.")

    if not user.is_active:
        write_audit_log(
            db,
            action="auth.login_failure",
            entity_type="user",
            entity_id=user.id,
            user=user,
            new_value_json={"email": credentials.email, "success": False},
            request=request,
            notes="Inactive account login attempt.",
            commit=True,
        )
        raise_unauthorized("User account is inactive.")

    access_token, expires_at = create_access_token(
        subject=user.id,
        role=user.role.value,
    )
    write_audit_log(
        db,
        action="auth.login_success",
        entity_type="user",
        entity_id=user.id,
        user=user,
        new_value_json={"email": user.email, "role": user.role.value, "success": True},
        request=request,
        commit=True,
    )

    return TokenResponse(
        access_token=access_token,
        expires_at=expires_at,
        user=UserRead.model_validate(user),
    )


@router.post("/logout", response_model=MessageResponse)
def logout(
    request: Request,
    context: Annotated[AuthContext, Depends(get_auth_context)],
    db: Annotated[Session, Depends(get_db)],
) -> MessageResponse:
    invalidate_access_token(context.token_id, context.token_expires_at_timestamp)
    write_audit_log(
        db,
        action="auth.logout",
        entity_type="user",
        entity_id=context.user.id,
        user=context.user,
        new_value_json={"token_id": context.token_id},
        request=request,
        commit=True,
    )
    return MessageResponse(message="Logged out successfully.")


@router.get("/me", response_model=UserRead)
def read_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserRead:
    return UserRead.model_validate(current_user)


@router.get("/admin-check", response_model=MessageResponse)
def admin_check(
    _admin: Annotated[User, Depends(require_admin)],
) -> MessageResponse:
    return MessageResponse(message="Admin access granted.")


@router.get("/branch-scope", response_model=BranchScopeResponse)
def read_branch_scope(
    branch_scope: Annotated[BranchScope, Depends(get_branch_scope)],
) -> BranchScopeResponse:
    return BranchScopeResponse(
        all_branches=branch_scope.all_branches,
        branch_ids=branch_scope.branch_ids,
    )
