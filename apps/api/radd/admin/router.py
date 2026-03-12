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
from radd.db.models import AuditLog, Customer, User, Workspace, RevenueEvent, RadarAlert, SmartRule as SmartRuleModel, FollowUpQueue
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


# ─── V2: Revenue Attribution ──────────────────────────────────────────────────

@router.get("/revenue/summary")
@limiter.limit(settings.default_rate_limit)
async def get_revenue_summary(
    request: Request,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
    period: str = Query("this_month", description="this_month | last_month | all_time"),
):
    """Revenue attribution summary for the dashboard."""
    from radd.revenue.attribution import get_revenue_summary
    async with get_db_session(current.workspace_id) as db:
        result = await db.execute(
            select(Workspace).where(Workspace.id == current.workspace_id)
        )
        ws = result.scalar_one_or_none()
        subscription_cost = float(ws.subscription_price_sar) if ws and ws.subscription_price_sar else 499.0
        summary = await get_revenue_summary(
            db_session=db,
            workspace_id=str(current.workspace_id),
            period=period,
            subscription_cost=subscription_cost,
        )
    return {
        "period": period,
        "total_attributed_sar": summary.total_attributed,
        "assisted_sales_sar": summary.assisted_sales,
        "returns_prevented_sar": summary.returns_prevented,
        "carts_recovered_sar": summary.carts_recovered,
        "upsells_sar": 0,
        "event_count": summary.assisted_sales_count + summary.returns_prevented_count + summary.carts_recovered_count,
        "roi_multiplier": summary.roi_multiple,
        "subscription_cost_sar": summary.subscription_cost,
    }


@router.get("/revenue/events")
@limiter.limit(settings.default_rate_limit)
async def list_revenue_events(
    request: Request,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Paginated list of revenue attribution events."""
    async with get_db_session(current.workspace_id) as db:
        total_result = await db.execute(
            select(func.count(RevenueEvent.id)).where(RevenueEvent.workspace_id == current.workspace_id)
        )
        total = total_result.scalar_one()
        result = await db.execute(
            select(RevenueEvent)
            .where(RevenueEvent.workspace_id == current.workspace_id)
            .order_by(RevenueEvent.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        events = result.scalars().all()
    return {
        "items": [
            {
                "id": str(e.id),
                "event_type": e.event_type,
                "amount_sar": float(e.amount_sar),
                "product_name": e.product_name,
                "order_id": e.order_id,
                "conversation_id": str(e.conversation_id) if e.conversation_id else None,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ],
        "total": total,
        "page": page,
    }


# ─── V2: Operational Radar ────────────────────────────────────────────────────

@router.get("/radar/alerts")
@limiter.limit(settings.default_rate_limit)
async def list_radar_alerts(
    request: Request,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
    unread_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """List operational radar alerts for this workspace."""
    async with get_db_session(current.workspace_id) as db:
        q = select(RadarAlert).where(RadarAlert.workspace_id == current.workspace_id)
        if unread_only:
            q = q.where(RadarAlert.is_read == False)
        total_result = await db.execute(select(func.count()).select_from(q.subquery()))
        total = total_result.scalar_one()
        q = q.order_by(RadarAlert.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(q)
        alerts = result.scalars().all()
    return {
        "items": [
            {
                "id": str(a.id),
                "alert_type": a.alert_type,
                "severity": a.severity,
                "title": a.title,
                "description": a.description,
                "suggested_action": a.suggested_action,
                "is_read": a.is_read,
                "created_at": a.created_at.isoformat(),
            }
            for a in alerts
        ],
        "total": total,
        "page": page,
    }


@router.post("/radar/scan")
@limiter.limit("5/minute")
async def trigger_radar_scan(
    request: Request,
    current: Annotated[CurrentUser, Depends(require_admin)],
):
    """Manually trigger an operational radar scan for this workspace."""
    from radd.radar.detector import scan_for_anomalies
    async with get_db_session(current.workspace_id) as db:
        alerts = await scan_for_anomalies(db_session=db, workspace_id=str(current.workspace_id))
        saved = []
        for alert in alerts:
            ra = RadarAlert(
                workspace_id=current.workspace_id,
                alert_type=alert.alert_type.value if hasattr(alert.alert_type, "value") else str(alert.alert_type),
                severity=alert.severity.value if hasattr(alert.severity, "value") else str(alert.severity),
                title=alert.title,
                description=alert.description,
                suggested_action=alert.suggested_action,
                metadata_=alert.metadata if hasattr(alert, "metadata") else {},
            )
            db.add(ra)
            saved.append({"alert_type": ra.alert_type, "severity": ra.severity, "title": ra.title})
        await db.flush()
    return {"scanned": True, "alerts_found": len(saved), "alerts": saved}


@router.patch("/radar/alerts/{alert_id}/read")
@limiter.limit(settings.default_rate_limit)
async def mark_alert_read(
    request: Request,
    alert_id: uuid.UUID,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
):
    async with get_db_session(current.workspace_id) as db:
        result = await db.execute(
            select(RadarAlert).where(
                RadarAlert.id == alert_id,
                RadarAlert.workspace_id == current.workspace_id,
            )
        )
        alert = result.scalar_one_or_none()
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        alert.is_read = True
    return {"marked_read": True}


# ─── V2: Smart Rules CRUD ─────────────────────────────────────────────────────

class SmartRuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True
    priority: int = 0
    triggers: list[dict] = []
    actions: list[dict] = []


@router.get("/rules")
@limiter.limit(settings.default_rate_limit)
async def list_smart_rules(
    request: Request,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
):
    """List all smart rules for this workspace."""
    async with get_db_session(current.workspace_id) as db:
        result = await db.execute(
            select(SmartRuleModel)
            .where(SmartRuleModel.workspace_id == current.workspace_id)
            .order_by(SmartRuleModel.priority.desc())
        )
        rules = result.scalars().all()
    return {
        "items": [
            {
                "id": str(r.id),
                "name": r.name,
                "description": r.description,
                "is_active": r.is_active,
                "priority": r.priority,
                "triggers": r.triggers,
                "actions": r.actions,
                "created_at": r.created_at.isoformat(),
            }
            for r in rules
        ]
    }


@router.post("/rules", status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.default_rate_limit)
async def create_smart_rule(
    request: Request,
    body: SmartRuleCreate,
    current: Annotated[CurrentUser, Depends(require_admin)],
):
    """Create a new smart rule."""
    async with get_db_session(current.workspace_id) as db:
        rule = SmartRuleModel(
            workspace_id=current.workspace_id,
            name=body.name,
            description=body.description,
            is_active=body.is_active,
            priority=body.priority,
            triggers=body.triggers,
            actions=body.actions,
        )
        db.add(rule)
        await db.flush()
    return {"id": str(rule.id), "name": rule.name, "created": True}


@router.patch("/rules/{rule_id}")
@limiter.limit(settings.default_rate_limit)
async def update_smart_rule(
    request: Request,
    rule_id: uuid.UUID,
    body: dict,
    current: Annotated[CurrentUser, Depends(require_admin)],
):
    """Update an existing smart rule (name, is_active, priority, triggers, actions)."""
    allowed = {"name", "description", "is_active", "priority", "triggers", "actions"}
    updates = {k: v for k, v in body.items() if k in allowed}
    async with get_db_session(current.workspace_id) as db:
        result = await db.execute(
            select(SmartRuleModel).where(
                SmartRuleModel.id == rule_id,
                SmartRuleModel.workspace_id == current.workspace_id,
            )
        )
        rule = result.scalar_one_or_none()
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
        for k, v in updates.items():
            setattr(rule, k, v)
    return {"updated": True}


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(settings.default_rate_limit)
async def delete_smart_rule(
    request: Request,
    rule_id: uuid.UUID,
    current: Annotated[CurrentUser, Depends(require_admin)],
):
    """Delete a smart rule."""
    async with get_db_session(current.workspace_id) as db:
        result = await db.execute(
            select(SmartRuleModel).where(
                SmartRuleModel.id == rule_id,
                SmartRuleModel.workspace_id == current.workspace_id,
            )
        )
        rule = result.scalar_one_or_none()
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
        await db.delete(rule)


# ─── V2: Salla Auto-Sync ──────────────────────────────────────────────────────

class SallaSyncRequest(BaseModel):
    salla_api_url: str = "https://api.salla.dev/admin/v2"
    salla_token: str


@router.post("/salla/sync")
@limiter.limit("10/minute")
async def trigger_salla_sync(
    request: Request,
    body: SallaSyncRequest,
    current: Annotated[CurrentUser, Depends(require_admin)],
):
    """Trigger a full Salla product + store policy sync into the KB."""
    from radd.onboarding.salla_sync import run_full_sync
    from radd.knowledge.service import KBService
    async with get_db_session(current.workspace_id) as db:
        kb_service = KBService(db=db, workspace_id=uuid.UUID(str(current.workspace_id)))
        result = await run_full_sync(
            workspace_id=str(current.workspace_id),
            salla_api_url=body.salla_api_url,
            salla_token=body.salla_token,
            db_session=db,
            kb_service=kb_service,
        )
    return {
        "synced": True,
        "products_synced": result.products_synced if hasattr(result, "products_synced") else 0,
        "documents_created": result.documents_created if hasattr(result, "documents_created") else 0,
    }


# ─── V2: Starter Packs ────────────────────────────────────────────────────────

class StarterPackRequest(BaseModel):
    sector: str  # perfumes | fashion | electronics | food


@router.post("/starter-pack")
@limiter.limit("5/minute")
async def apply_starter_pack(
    request: Request,
    body: StarterPackRequest,
    current: Annotated[CurrentUser, Depends(require_admin)],
):
    """Apply a sector-specific starter pack (pre-built KB + keywords) to this workspace."""
    from radd.sales.engine import apply_starter_pack
    from radd.knowledge.service import KBService
    async with get_db_session(current.workspace_id) as db:
        kb_service = KBService(db=db, workspace_id=uuid.UUID(str(current.workspace_id)))
        result = await apply_starter_pack(
            workspace_id=str(current.workspace_id),
            sector=body.sector,
            kb_service=kb_service,
        )
        # Save sector to workspace
        ws_result = await db.execute(
            select(Workspace).where(Workspace.id == current.workspace_id)
        )
        ws = ws_result.scalar_one_or_none()
        if ws:
            ws.sector = body.sector
    return result


# ─── V3: RADD Score ───────────────────────────────────────────────────────────

@router.get("/radd-score")
@limiter.limit(settings.default_rate_limit)
async def get_radd_score(
    request: Request,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
    period_days: int = Query(30, ge=7, le=365),
):
    """Get RADD Score (0-100) for this workspace."""
    from radd.analytics.radd_score import calculate_radd_score
    async with get_db_session(current.workspace_id) as db:
        score = await calculate_radd_score(db, str(current.workspace_id), period_days)
    return {
        "total": score.total,
        "grade": score.grade,
        "summary_ar": score.summary_ar,
        "breakdown": {
            "automation": score.automation_score,
            "quality": score.quality_score,
            "escalation_health": score.escalation_score,
            "knowledge_coverage": score.knowledge_score,
            "customer_happiness": score.happiness_score,
        },
        "period_days": period_days,
    }


# ─── V3: Churn Radar ─────────────────────────────────────────────────────────

@router.get("/churn-radar")
@limiter.limit(settings.default_rate_limit)
async def get_churn_radar(
    request: Request,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
    inactive_days: int = Query(45, ge=7, le=180),
):
    """Detect customers at churn risk."""
    from radd.analytics.churn_radar import scan_for_churn_risk, get_churn_summary
    async with get_db_session(current.workspace_id) as db:
        alerts = await scan_for_churn_risk(db, str(current.workspace_id), inactive_days)
    summary = get_churn_summary(alerts)
    return {
        "summary": summary,
        "alerts": [
            {
                "customer_id": a.customer_id,
                "customer_tier": a.customer_tier,
                "risk_level": a.risk_level.value,
                "reason": a.reason,
                "days_inactive": a.days_inactive,
                "total_revenue": a.total_revenue,
                "suggested_action": a.suggested_action,
                "last_seen_at": a.last_seen_at,
            }
            for a in alerts[:100]
        ],
    }


# ─── V3: Agent Performance ────────────────────────────────────────────────────

@router.get("/agent-performance")
@limiter.limit(settings.default_rate_limit)
async def get_agent_performance(
    request: Request,
    current: Annotated[CurrentUser, Depends(require_admin)],
    period_days: int = Query(30, ge=7, le=365),
):
    """Get performance metrics for all agents."""
    from radd.analytics.agent_performance import get_agent_performance, get_team_summary
    async with get_db_session(current.workspace_id) as db:
        metrics = await get_agent_performance(db, str(current.workspace_id), period_days)
    summary = get_team_summary(metrics)
    return {
        "summary": summary,
        "agents": [
            {
                "user_id": m.user_id,
                "agent_name": m.agent_name,
                "total_assigned": m.total_assigned,
                "total_resolved": m.total_resolved,
                "resolution_rate": m.resolution_rate,
                "avg_resolution_minutes": m.avg_resolution_minutes,
                "avg_first_response_minutes": m.avg_first_response_minutes,
                "estimated_csat": m.estimated_csat,
            }
            for m in metrics
        ],
        "period_days": period_days,
    }


# ─── V3: Follow-ups ──────────────────────────────────────────────────────────

@router.get("/followups/stats")
@limiter.limit(settings.default_rate_limit)
async def get_followup_stats(
    request: Request,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
):
    """Get follow-up queue statistics."""
    from radd.followups.scheduler import get_followup_stats
    async with get_db_session(current.workspace_id) as db:
        stats = await get_followup_stats(db, str(current.workspace_id))
    return stats


@router.post("/followups/process")
@limiter.limit("10/minute")
async def process_followups(
    request: Request,
    current: Annotated[CurrentUser, Depends(require_admin)],
):
    """Manually trigger follow-up processing (normally runs on schedule)."""
    from radd.followups.scheduler import process_due_followups
    async with get_db_session(current.workspace_id) as db:
        processed = await process_due_followups(db, str(current.workspace_id))
    return {"processed": len(processed), "items": processed}


# ─── V3: Salla Advanced Actions ───────────────────────────────────────────────

class CancelOrderRequest(BaseModel):
    order_reference: str
    salla_token: str
    reason: str = "change_mind"


class TrackShipmentRequest(BaseModel):
    order_reference: str
    salla_token: str


@router.post("/salla/cancel-order")
@limiter.limit("20/minute")
async def cancel_salla_order(
    request: Request,
    body: CancelOrderRequest,
    current: Annotated[CurrentUser, Depends(require_admin)],
):
    """Cancel a Salla order by reference number."""
    from radd.actions.salla_advanced import cancel_order
    result = await cancel_order(
        order_reference=body.order_reference,
        access_token=body.salla_token,
        reason=body.reason,
    )
    return result


@router.post("/salla/track-shipment")
@limiter.limit("30/minute")
async def track_salla_shipment(
    request: Request,
    body: TrackShipmentRequest,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
):
    """Get real shipment tracking info for a Salla order."""
    from radd.actions.salla_advanced import track_shipment
    result = await track_shipment(
        order_reference=body.order_reference,
        access_token=body.salla_token,
    )
    return result


# ─── V3: Agent Assist ─────────────────────────────────────────────────────────

@router.get("/escalations/{escalation_id}/assist")
@limiter.limit(settings.default_rate_limit)
async def get_agent_assist(
    request: Request,
    escalation_id: uuid.UUID,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
):
    """Get AI-generated reply suggestion for an escalated conversation."""
    from radd.db.models import EscalationEvent, Conversation, Customer, Message as MsgModel
    from radd.intelligence.agent_assist import generate_agent_suggestion
    from sqlalchemy import select as sa_select

    async with get_db_session(current.workspace_id) as db:
        esc_result = await db.execute(
            sa_select(EscalationEvent).where(
                EscalationEvent.id == escalation_id,
                EscalationEvent.workspace_id == current.workspace_id,
            )
        )
        esc = esc_result.scalar_one_or_none()
        if not esc:
            raise HTTPException(status_code=404, detail="Escalation not found")

        # Get conversation + customer
        conv_result = await db.execute(
            sa_select(Conversation).where(Conversation.id == esc.conversation_id)
        )
        conversation = conv_result.scalar_one_or_none()

        cust_result = await db.execute(
            sa_select(Customer).where(Customer.id == conversation.customer_id)
        )
        customer = cust_result.scalar_one_or_none()

        # Get recent messages
        msgs_result = await db.execute(
            sa_select(MsgModel)
            .where(MsgModel.conversation_id == esc.conversation_id)
            .order_by(MsgModel.created_at.desc())
            .limit(8)
        )
        messages = [
            {"sender_type": m.sender_type, "content": m.content}
            for m in reversed(msgs_result.scalars().all())
        ]

    from radd.customers.context_builder import build_customer_context
    customer_ctx = build_customer_context(customer) if customer else ""

    last_msg = messages[-1]["content"] if messages else ""
    suggestion = await generate_agent_suggestion(
        customer_message=last_msg,
        conversation_history=messages,
        customer_context=customer_ctx,
        kb_passages=[],
        dialect=conversation.dialect or "gulf",
        escalation_reason=esc.reason or "",
    )

    return {
        "escalation_id": str(escalation_id),
        "suggestion": suggestion.get("suggestion", ""),
        "recommended_action": suggestion.get("recommended_action", "respond"),
        "confidence": suggestion.get("confidence", 0),
        "context": {
            "customer_tier": customer.customer_tier if customer else "new",
            "total_escalations": customer.total_escalations if customer else 0,
            "dialect": conversation.dialect,
            "stage": getattr(conversation, "stage", "unknown"),
        },
    }


# ─── V3: Create Return (Salla) ────────────────────────────────────────────────

class CreateReturnRequest(BaseModel):
    order_reference: str
    salla_token: str
    reason: str = "wrong_item"


@router.post("/salla/create-return")
@limiter.limit("20/minute")
async def create_salla_return(
    request: Request,
    body: CreateReturnRequest,
    current: Annotated[CurrentUser, Depends(require_admin)],
):
    """Create a return request for a Salla order."""
    from radd.actions.salla_advanced import create_return_request
    result = await create_return_request(
        order_reference=body.order_reference,
        access_token=body.salla_token,
        reason=body.reason,
    )
    return result
