"""
Non-interactive seed script: creates a workspace + superadmin user.
Usage: uv run python scripts/seed_superadmin.py
"""
import asyncio
import sys
import uuid

sys.path.insert(0, ".")

from sqlalchemy import select, text

import bcrypt
from radd.db.models import User, Workspace
from radd.db.session import get_db_session


def hash_password_direct(password: str) -> str:
    """Hash password using bcrypt directly (bypasses passlib compatibility issue)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


WORKSPACE_SLUG = "radd-hq"
WORKSPACE_NAME = "Radd HQ"
SUPERADMIN_EMAIL = "admin@radd.ai"
SUPERADMIN_PASSWORD = "Radd@2026!"
SUPERADMIN_NAME = "Super Admin"


async def main() -> None:
    print("=== Radd — Seed Workspace + Superadmin ===\n")

    async with get_db_session() as db:
        # 1. Create workspace if not exists
        ws = (
            await db.execute(select(Workspace).where(Workspace.slug == WORKSPACE_SLUG))
        ).scalar_one_or_none()

        if not ws:
            ws = Workspace(
                id=uuid.uuid4(),
                name=WORKSPACE_NAME,
                slug=WORKSPACE_SLUG,
                status="active",
            )
            db.add(ws)
            await db.flush()
            print(f"✅ Workspace created: {WORKSPACE_NAME} ({WORKSPACE_SLUG})")

            # Set RLS variable for this session
            await db.execute(
                text(f"SET app.current_workspace_id = '{ws.id}'")
            )
        else:
            print(f"ℹ️  Workspace already exists: {WORKSPACE_SLUG}")
            await db.execute(
                text(f"SET app.current_workspace_id = '{ws.id}'")
            )

        # 2. Create superadmin user if not exists
        existing = (
            await db.execute(
                select(User).where(
                    User.workspace_id == ws.id,
                    User.email == SUPERADMIN_EMAIL,
                )
            )
        ).scalar_one_or_none()

        if existing:
            existing.is_superadmin = True
            existing.is_active = True
            print(f"ℹ️  User '{SUPERADMIN_EMAIL}' promoted to superadmin.")
        else:
            user = User(
                id=uuid.uuid4(),
                workspace_id=ws.id,
                email=SUPERADMIN_EMAIL,
                name=SUPERADMIN_NAME,
                role="owner",
                password_hash=hash_password_direct(SUPERADMIN_PASSWORD),
                is_active=True,
                is_superadmin=True,
            )
            db.add(user)
            await db.flush()
            print(f"✅ Superadmin user created:")
            print(f"   Email:     {SUPERADMIN_EMAIL}")
            print(f"   Password:  {SUPERADMIN_PASSWORD}")
            print(f"   Workspace: {WORKSPACE_SLUG}")
            print(f"   Role:      owner + superadmin")

        await db.commit()

    print(f"\n🚀 Done! Login at /login with:")
    print(f"   Workspace: {WORKSPACE_SLUG}")
    print(f"   Email:     {SUPERADMIN_EMAIL}")
    print(f"   Password:  {SUPERADMIN_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())
