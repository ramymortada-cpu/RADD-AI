from __future__ import annotations
import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from radd.auth.service import decode_token
from radd.db.models import User
from radd.db.session import get_db_session

bearer_scheme = HTTPBearer()


class CurrentUser:
    def __init__(self, user: User, workspace_id: uuid.UUID):
        self.user = user
        self.workspace_id = workspace_id
        self.role = user.role


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> CurrentUser:
    try:
        payload = decode_token(credentials.credentials)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not an access token")

    user_id = uuid.UUID(payload["sub"])
    workspace_id = uuid.UUID(payload["workspace_id"])

    async with get_db_session(workspace_id) as db:
        result = await db.execute(select(User).where(User.id == user_id, User.is_active.is_(True)))
        user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return CurrentUser(user=user, workspace_id=workspace_id)


def require_role(*roles: str):
    """Dependency factory: require one of the given roles."""
    async def _check(current: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        if current.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current
    return _check


# Convenience role dependencies
require_owner = require_role("owner")
require_admin = require_role("owner", "admin")
require_agent = require_role("owner", "admin", "agent")
require_reviewer = require_role("owner", "admin", "agent", "reviewer")
