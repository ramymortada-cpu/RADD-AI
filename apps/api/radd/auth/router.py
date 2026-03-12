from __future__ import annotations
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials
from radd.limiter import limiter
from radd.config import settings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from radd.auth.middleware import CurrentUser, bearer_scheme, get_current_user
from radd.auth.schemas import LoginRequest, RefreshRequest, TokenResponse, UserResponse
from radd.auth.service import (
    authenticate_user,
    blacklist_token,
    create_access_token,
    create_refresh_token,
    decode_token,
    is_token_blacklisted,
)
from radd.db.models import User, Workspace
from radd.db.session import get_db_session

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.auth_rate_limit)
async def login(request: Request, body: LoginRequest):
    async with get_db_session() as db:
        result = await db.execute(
            select(Workspace).where(Workspace.slug == body.workspace_slug, Workspace.status == "active")
        )
        workspace = result.scalar_one_or_none()

    if not workspace:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    async with get_db_session(workspace.id) as db:
        user = await authenticate_user(db, workspace.id, body.email, body.password)

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    return TokenResponse(
        access_token=create_access_token(user.id, workspace.id, user.role, user.is_superadmin),
        refresh_token=create_refresh_token(user.id, workspace.id),
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(settings.auth_rate_limit)
async def refresh(request: Request, body: RefreshRequest):
    try:
        payload = decode_token(body.refresh_token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not a refresh token")

    # Check if refresh token was explicitly revoked (logout)
    if await is_token_blacklisted(body.refresh_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked")

    import uuid
    user_id = uuid.UUID(payload["sub"])
    workspace_id = uuid.UUID(payload["workspace_id"])

    async with get_db_session(workspace_id) as db:
        result = await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))
        user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # Rotate: blacklist old refresh token, issue new pair
    from datetime import timezone
    old_exp = payload.get("exp", 0)
    remaining_seconds = max(0, int(old_exp - datetime.now(timezone.utc).timestamp()))
    if remaining_seconds > 0:
        await blacklist_token(body.refresh_token, remaining_seconds)

    return TokenResponse(
        access_token=create_access_token(user.id, workspace_id, user.role, user.is_superadmin),
        refresh_token=create_refresh_token(user.id, workspace_id),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(settings.auth_rate_limit)
async def logout(
    request: Request,
    body: RefreshRequest,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
):
    """
    Logout: blacklist both the current access token and the provided refresh token.
    Client sends: Authorization: Bearer <access_token>, body: { refresh_token }.
    """
    from datetime import timezone

    # Blacklist access token — invalidates session immediately
    access_token = credentials.credentials
    try:
        payload = decode_token(access_token)
        exp = payload.get("exp", 0)
        remaining = max(0, int(exp - datetime.now(timezone.utc).timestamp()))
        if remaining > 0:
            await blacklist_token(access_token, remaining)
    except ValueError:
        pass

    # Blacklist refresh token — prevents token rotation
    try:
        payload = decode_token(body.refresh_token)
        old_exp = payload.get("exp", 0)
        remaining = max(0, int(old_exp - datetime.now(timezone.utc).timestamp()))
        if remaining > 0:
            await blacklist_token(body.refresh_token, remaining)
    except ValueError:
        pass


@router.get("/me", response_model=UserResponse)
async def me(current: Annotated[CurrentUser, Depends(get_current_user)]):
    return UserResponse.model_validate(current.user)
