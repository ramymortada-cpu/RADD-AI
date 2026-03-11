from __future__ import annotations
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from radd.auth.middleware import CurrentUser, get_current_user
from radd.auth.schemas import LoginRequest, RefreshRequest, TokenResponse, UserResponse
from radd.auth.service import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from radd.db.models import User, Workspace
from radd.db.session import get_db_session

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
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
        access_token=create_access_token(user.id, workspace.id, user.role),
        refresh_token=create_refresh_token(user.id, workspace.id),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest):
    try:
        payload = decode_token(body.refresh_token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not a refresh token")

    import uuid
    user_id = uuid.UUID(payload["sub"])
    workspace_id = uuid.UUID(payload["workspace_id"])

    async with get_db_session(workspace_id) as db:
        result = await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))
        user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return TokenResponse(
        access_token=create_access_token(user.id, workspace_id, user.role),
        refresh_token=create_refresh_token(user.id, workspace_id),
    )


@router.get("/me", response_model=UserResponse)
async def me(current: Annotated[CurrentUser, Depends(get_current_user)]):
    return UserResponse.model_validate(current.user)
