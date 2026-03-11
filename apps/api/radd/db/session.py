from __future__ import annotations
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from radd.db.base import AsyncSessionLocal


@asynccontextmanager
async def get_db_session(workspace_id: uuid.UUID | None = None) -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions with RLS tenant isolation.
    Sets app.current_workspace_id for every session so RLS policies apply.
    """
    async with AsyncSessionLocal() as session:
        if workspace_id is not None:
            await session.execute(
                text("SET LOCAL app.current_workspace_id = :wid"),
                {"wid": str(workspace_id)},
            )
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db(workspace_id: uuid.UUID | None = None) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for injecting a DB session."""
    async with get_db_session(workspace_id) as session:
        yield session
