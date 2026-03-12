from __future__ import annotations

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from radd.limiter import limiter
from radd.config import settings
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from radd.admin.analytics import get_kpis
from radd.auth.middleware import CurrentUser, require_admin, require_owner, require_reviewer
from radd.auth.service import hash_password
from radd.db.models import AuditLog, Customer, User, Workspace
from radd.db.session import get_db_session

router = APIRouter(prefix="/admin", tags=["admin"])


# ─── KPI dashboard ────────────────────────────────────────────────────────────

@router.get("/analytics")
@limiter.limit(settings.default_rate_limit)
async def get_analytics(request: Request, current: Annotated[CurrentUser, Depends(require_reviewer)]):
    """8 KPI cards for the dashboard."""
    async with get_db_session(current.workspace_id) as db:
        kpis = await get_kpis(db, current.workspace_id)
    return kpis


# ─── Workspace settings ───────────────────────────────────────────────────────

# ─── Customer profiles ────────────────────────────────────────────────────────

@router.get("/customers")
@limiter.limit(settings.default_rate_limit)
async def list_customers(
    request: Request,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
    tier: Optional[str] = Query(None, description="Filter by tier: new, standard, returning, vip, at_risk"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """List customers with their profiles — for the Merchant Memory dashboard."""
    async with get_db_session(current.workspace_id) as db:
        q = select(Customer).where(Customer.workspace_id == current.workspace_id)
        if tier:
            q = q.where(Customer.customer_tier == tier)

        total_result = await db.execute(select(func.count()).select_from(q.subquery()))
        total = total_result.scalar_one()

        q = q.order_by(Customer.total_conversations.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(q)
        customers = result.scalars().all()

    return {
        "items": [
            {
                "id": str(c.id),
                "display_name": c.display_name,
                "phone_hash": c.phone_hash,
                "customer_tier": c.customer_tier,
                "total_conversations": c.total_conversations,
                "total_escalations": c.total_escalations,
                "avg_sentiment": float(c.avg_sentiment) if c.avg_sentiment is not None else None,
                "salla_total_orders": c.salla_total_orders,
                "salla_total_revenue": float(c.salla_total_revenue) if c.salla_total_revenue else 0,
                "last_seen_at": c.last_seen_at.isoformat() if c.last_seen_at else None,
                "last_complaint_at": c.last_complaint_at.isoformat() if c.last_complaint_at else None,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in customers
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ─── Shadow Mode toggle ───────────────────────────────────────────────────────

class ShadowModeUpdate(BaseModel):
    enabled: bool


@router.get("/shadow-mode")
@limiter.limit(settings.default_rate_limit)
async def get_shadow_mode(
    request: Request,
    current: Annotated[CurrentUser, Depends(require_admin)],
):
    """Return current shadow mode state."""
    return {"shadow_mode": settings.shadow_mode}


@router.post("/shadow-mode")
@limiter.limit(settings.default_rate_limit)
async def set_shadow_mode(
    request: Request,
    body: ShadowModeUpdate,
    current: Annotated[CurrentUser, Depends(require_admin)],
):
    """Toggle shadow mode at runtime (persists until next restart unless env is set)."""
    settings.shadow_mode = body.enabled
    return {"shadow_mode": settings.shadow_mode, "message": "تم التحديث"}


# ─────────────────────────────────────────────────────────────────────────────

class SettingsUpdate(BaseModel):
    confidence_auto_threshold: Optional[float] = None
    confidence_soft_escalation_threshold: Optional[float] = None
    business_hours: Optional[dict] = None
    store_name: Optional[str] = None
    escalation_message_gulf: Optional[str] = None
    escalation_message_msa: Optional[str] = None


@router.get("/settings")
@limiter.limit(settings.default_rate_limit)
async def get_settings(request: Request, current: Annotated[CurrentUser, Depends(require_reviewer)]):
    async with get_db_session() as db:
        result = await db.execute(
            select(Workspace).where(Workspace.id == current.workspace_id)
        )
        ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {
        "workspace_id": str(ws.id),
        "name": ws.name,
        "slug": ws.slug,
        "plan": ws.plan,
        "settings": ws.settings or {},
    }


@router.patch("/settings")
@limiter.limit(settings.default_rate_limit)
async def update_settings(
    request: Request,
    body: SettingsUpdate,
    current: Annotated[CurrentUser, Depends(require_admin)],
):
    async with get_db_session() as db:
        result = await db.execute(
            select(Workspace).where(Workspace.id == current.workspace_id)
        )
        ws = result.scalar_one_or_none()
        if not ws:
            raise HTTPException(status_code=404, detail="Workspace not found")

        settings = dict(ws.settings or {})
        update_data = body.model_dump(exclude_none=True)
        settings.update(update_data)
        ws.settings = settings

    return {"updated": True, "settings": settings}


# ─── Audit log ────────────────────────────────────────────────────────────────

@router.get("/audit-log")
@limiter.limit(settings.default_rate_limit)
async def get_audit_log(
    request: Request,
    current: Annotated[CurrentUser, Depends(require_admin)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    action_filter: Optional[str] = Query(None, alias="action"),
):
    async with get_db_session(current.workspace_id) as db:
        q = select(AuditLog).where(AuditLog.workspace_id == current.workspace_id)
        if action_filter:
            q = q.where(AuditLog.action.ilike(f"%{action_filter}%"))

        total_result = await db.execute(select(func.count()).select_from(q.subquery()))
        total = total_result.scalar_one()

        q = q.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(q)
        entries = result.scalars().all()

    return {
        "items": [
            {
                "id": e.id,
                "action": e.action,
                "entity_type": e.entity_type,
                "entity_id": str(e.entity_id) if e.entity_id else None,
                "user_id": str(e.user_id) if e.user_id else None,
                "details": e.details,
                "ip_address": e.ip_address,
                "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ─── User management ──────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    name: str
    role: str
    password: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


@router.get("/users", response_model=list[UserResponse])
@limiter.limit(settings.default_rate_limit)
async def list_users(request: Request, current: Annotated[CurrentUser, Depends(require_admin)]):
    async with get_db_session(current.workspace_id) as db:
        result = await db.execute(
            select(User).where(User.workspace_id == current.workspace_id)
            .order_by(User.created_at.asc())
        )
        users = result.scalars().all()
    return [UserResponse.model_validate(u) for u in users]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.default_rate_limit)
async def create_user(
    request: Request,
    body: UserCreate,
    current: Annotated[CurrentUser, Depends(require_admin)],
):
    valid_roles = ("owner", "admin", "agent", "reviewer")
    if body.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Role must be one of {valid_roles}")

    async with get_db_session(current.workspace_id) as db:
        existing = await db.execute(
            select(User).where(
                User.workspace_id == current.workspace_id,
                User.email == body.email,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Email already exists in workspace")

        user = User(
            workspace_id=current.workspace_id,
            email=body.email,
            name=body.name,
            role=body.role,
            password_hash=hash_password(body.password),
            is_active=True,
        )
        db.add(user)
        await db.flush()

    return UserResponse.model_validate(user)


@router.patch("/users/{user_id}")
@limiter.limit(settings.default_rate_limit)
async def update_user(
    request: Request,
    user_id: uuid.UUID,
    body: dict,
    current: Annotated[CurrentUser, Depends(require_admin)],
):
    allowed = {"role", "is_active", "name"}
    updates = {k: v for k, v in body.items() if k in allowed}

    async with get_db_session(current.workspace_id) as db:
        result = await db.execute(
            select(User).where(User.id == user_id, User.workspace_id == current.workspace_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user.role == "owner" and current.role != "owner":
            raise HTTPException(status_code=403, detail="Cannot modify owner account")

        for k, v in updates.items():
            setattr(user, k, v)

    return UserResponse.model_validate(user)
