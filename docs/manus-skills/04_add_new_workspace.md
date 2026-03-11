# Skill: Create a New Merchant Workspace

## When to Use
When onboarding a new merchant/store to the platform.

## Method: Via Seed Script

### Step 1: Create a seed script for the new workspace
```python
# scripts/create_workspace.py
import asyncio
import uuid
import hashlib
from radd.db.session import get_db_session
from radd.db.models import Workspace, User, Channel
from radd.auth.service import hash_password

NEW_WORKSPACE = {
    "name": "متجر الرياض",           # Store name
    "slug": "riyadh-store",          # Unique URL slug (English, no spaces)
    "plan": "pilot",                  # pilot | growth | scale
}

OWNER_USER = {
    "email": "owner@riyadh-store.com",
    "password": "SecurePass123!",
    "name": "أحمد المالك",
    "role": "owner",
}

WHATSAPP_CHANNEL = {
    "type": "whatsapp",
    "name": "قناة واتساب الرئيسية",
    "config": {
        "wa_phone_number_id": "YOUR_PHONE_NUMBER_ID",
        "wa_business_account_id": "YOUR_BUSINESS_ACCOUNT_ID",
    }
}

async def create_workspace():
    ws_id = uuid.uuid4()
    
    # Use get_db_session without workspace_id for creation
    from radd.db.base import async_session_factory
    from sqlalchemy import text
    
    async with async_session_factory() as db:
        # Create workspace
        workspace = Workspace(
            id=ws_id,
            name=NEW_WORKSPACE["name"],
            slug=NEW_WORKSPACE["slug"],
            plan=NEW_WORKSPACE["plan"],
            status="active",
            settings={
                "confidence_auto_threshold": 0.85,
                "confidence_soft_escalation_threshold": 0.60,
            }
        )
        db.add(workspace)
        await db.flush()
        
        # Create owner user
        user = User(
            workspace_id=ws_id,
            email=OWNER_USER["email"],
            password_hash=hash_password(OWNER_USER["password"]),
            name=OWNER_USER["name"],
            role=OWNER_USER["role"],
            is_active=True,
        )
        db.add(user)
        
        # Create WhatsApp channel
        channel = Channel(
            workspace_id=ws_id,
            type=WHATSAPP_CHANNEL["type"],
            name=WHATSAPP_CHANNEL["name"],
            is_active=True,
            config=WHATSAPP_CHANNEL["config"],
        )
        db.add(channel)
        await db.commit()
        
        print(f"✅ Workspace created!")
        print(f"   ID: {ws_id}")
        print(f"   Slug: {NEW_WORKSPACE['slug']}")
        print(f"   Login: {OWNER_USER['email']} / {OWNER_USER['password']}")

asyncio.run(create_workspace())
```

### Step 2: Run it
```bash
cd apps/api
uv run python scripts/create_workspace.py
```

### Step 3: Verify
```bash
# Login with new credentials
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_slug": "riyadh-store",
    "email": "owner@riyadh-store.com",
    "password": "SecurePass123!"
  }'
```

## Adding More Users to Existing Workspace

```bash
# Login as admin first to get token
TOKEN="eyJ..."

# Create agent user
curl -X POST http://localhost:8000/api/v1/admin/users \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "فاطمة موظفة الدعم",
    "email": "fatima@riyadh-store.com",
    "role": "agent",
    "password": "AgentPass123!"
  }'
```

## Role Permissions Summary
| Role | Can do |
|------|--------|
| `owner` | Everything including deleting workspace |
| `admin` | Manage users, approve KB, change settings |
| `agent` | Reply to conversations, accept escalations |
| `reviewer` | Read-only: analytics, conversations, KB |
