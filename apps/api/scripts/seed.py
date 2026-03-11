"""
Seed development data: 1 workspace, 1 owner, 1 agent, 1 WhatsApp channel.
Run with: make seed
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from radd.auth.service import hash_password
from radd.db.base import AsyncSessionLocal, engine
from radd.db.models import Base, Channel, User, Workspace


async def seed():
    print("Seeding development data...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Check if already seeded
        result = await db.execute(text("SELECT COUNT(*) FROM workspaces"))
        count = result.scalar()
        if count > 0:
            print("Database already seeded. Skipping.")
            return

        # Create workspace (no RLS needed for initial seed)
        workspace = Workspace(
            name="Demo Store — متجر تجريبي",
            slug="demo-store",
            settings={
                "confidence_auto_threshold": 0.85,
                "confidence_soft_escalation_threshold": 0.60,
                "business_hours": {"start": "09:00", "end": "22:00", "timezone": "Asia/Riyadh"},
            },
            plan="pilot",
            status="active",
        )
        db.add(workspace)
        await db.flush()

        # Set RLS context for subsequent inserts
        await db.execute(
            text("SET LOCAL app.current_workspace_id = :wid"),
            {"wid": str(workspace.id)},
        )

        # Owner user
        owner = User(
            workspace_id=workspace.id,
            email="owner@demo-store.sa",
            password_hash=hash_password("demo_owner_2026"),
            name="مدير المتجر",
            role="owner",
            is_active=True,
        )
        db.add(owner)

        # Agent user
        agent = User(
            workspace_id=workspace.id,
            email="agent@demo-store.sa",
            password_hash=hash_password("demo_agent_2026"),
            name="موظف خدمة العملاء",
            role="agent",
            is_active=True,
        )
        db.add(agent)

        # WhatsApp channel (config left empty for dev; fill real values in .env)
        channel = Channel(
            workspace_id=workspace.id,
            type="whatsapp",
            name="واتساب الرئيسي",
            is_active=True,
            config={
                "wa_phone_number_id": "",
                "wa_business_account_id": "",
                "wa_api_token_ref": "env:WA_API_TOKEN",
            },
        )
        db.add(channel)

        await db.commit()

    print("✓ Seeded:")
    print("  Workspace: Demo Store (slug: demo-store)")
    print("  Owner:     owner@demo-store.sa / demo_owner_2026")
    print("  Agent:     agent@demo-store.sa / demo_agent_2026")
    print("  Channel:   WhatsApp (config needs WA credentials in .env)")
    print()
    print("  API docs:  http://localhost:8000/docs")
    print("  Health:    http://localhost:8000/health")


if __name__ == "__main__":
    asyncio.run(seed())
