from __future__ import annotations
"""
V4 Admin Sub-Router — Intelligence, Integrations, Channels.
Extracted from admin/router.py to keep it below 500 lines.
"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import select

from radd.auth.middleware import CurrentUser, require_admin, require_owner, require_reviewer
from radd.config import settings
from radd.db.session import get_db_session
from radd.limiter import limiter

router = APIRouter(prefix="/admin", tags=["admin-v4"])


# ─── Cross-Merchant Intelligence ─────────────────────────────────────────────

@router.get("/benchmark")
@limiter.limit(settings.default_rate_limit)
async def get_benchmark(
    request: Request,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
    period_days: int = Query(30, ge=7, le=90),
):
    """Cross-merchant benchmark comparison for this workspace's sector."""
    from radd.intelligence.cross_merchant import get_merchant_benchmark_report
    async with get_db_session(current.workspace_id) as db:
        report = await get_merchant_benchmark_report(db, str(current.workspace_id), period_days)
    if not report:
        return {"available": False, "reason": "لا توجد بيانات كافية بعد أو لا يوجد متاجر مماثلة"}
    return {
        "available": True,
        "sector": report.sector,
        "my_automation_rate": report.my_automation_rate,
        "my_escalation_rate": report.my_escalation_rate,
        "sector_avg_automation": report.sector_avg_automation,
        "sector_avg_escalation": report.sector_avg_escalation,
        "peer_count": report.peer_count,
        "percentile": report.percentile,
        "gap_analysis": report.gap_analysis,
        "recommendations": report.recommendations,
    }


# ─── Seasonal Auto-Prep ───────────────────────────────────────────────────────

@router.get("/seasonal/upcoming")
@limiter.limit(settings.default_rate_limit)
async def get_upcoming_seasons(
    request: Request,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
    days_ahead: int = Query(60, ge=7, le=180),
):
    """Upcoming seasons/holidays with KB preparation recommendations."""
    from radd.intelligence.seasonal_prep import get_upcoming_seasons as _get_seasons
    from radd.db.models import Workspace as WsModel

    async with get_db_session(current.workspace_id) as db:
        ws_result = await db.execute(
            select(WsModel).where(WsModel.id == current.workspace_id)
        )
        ws = ws_result.scalar_one_or_none()
        sector = ws.sector if ws else "other"

    alerts = _get_seasons(days_ahead=days_ahead, sector=sector)
    return {
        "seasons": [
            {
                "name_ar": a.season.name_ar,
                "name_en": a.season.name_en,
                "days_until": a.days_until,
                "urgency": a.urgency,
                "message_ar": a.message_ar,
                "traffic_multiplier": a.season.traffic_multiplier,
                "kb_topics": a.kb_topics,
            }
            for a in alerts
        ],
        "total": len(alerts),
    }


class GenerateSeasonalKBRequest(BaseModel):
    season_name: str
    sector: str = "other"


@router.post("/seasonal/generate-kb")
@limiter.limit("5/minute")
async def generate_seasonal_kb(
    request: Request,
    body: GenerateSeasonalKBRequest,
    current: Annotated[CurrentUser, Depends(require_admin)],
):
    """Generate and import seasonal KB content using GPT."""
    from radd.intelligence.seasonal_prep import generate_seasonal_kb_content
    from radd.knowledge.service import KBService

    async with get_db_session(current.workspace_id) as db:
        result_data = await generate_seasonal_kb_content(
            season_name=body.season_name,
            sector=body.sector,
        )
        if result_data.get("kb_content"):
            kb = KBService(db=db, workspace_id=current.workspace_id)
            doc = await kb.create_document(
                title=result_data["kb_title"],
                content=result_data["kb_content"],
                content_type="seasonal",
            )
            return {"created": True, "doc_id": str(doc.id), "pairs_count": len(result_data.get("pairs", []))}

    return {"created": False, "error": "فشل توليد المحتوى"}


# ─── Zid Sync ─────────────────────────────────────────────────────────────────

class ZidSyncRequest(BaseModel):
    zid_token: str
    store_id: str = ""


@router.post("/zid/sync")
@limiter.limit("10/minute")
async def trigger_zid_sync(
    request: Request,
    body: ZidSyncRequest,
    current: Annotated[CurrentUser, Depends(require_admin)],
):
    """Sync products and policies from Zid store to KB."""
    from radd.onboarding.zid_sync import sync_zid_store
    from radd.knowledge.service import KBService

    async with get_db_session(current.workspace_id) as db:
        kb = KBService(db=db, workspace_id=current.workspace_id)
        result = await sync_zid_store(
            workspace_id=str(current.workspace_id),
            access_token=body.zid_token,
            store_id=body.store_id,
            kb_service=kb,
        )
    return result


# ─── Instagram Channel Setup ──────────────────────────────────────────────────

class InstagramSetupRequest(BaseModel):
    ig_page_id: str
    page_access_token: str


@router.post("/channels/instagram")
@limiter.limit("10/minute")
async def setup_instagram_channel(
    request: Request,
    body: InstagramSetupRequest,
    current: Annotated[CurrentUser, Depends(require_owner)],
):
    """Configure Instagram DM channel for this workspace."""
    from radd.db.models import Channel
    async with get_db_session(current.workspace_id) as db:
        result = await db.execute(
            select(Channel).where(
                Channel.workspace_id == current.workspace_id,
                Channel.type == "instagram",
            )
        )
        channel = result.scalar_one_or_none()

        from radd.utils.crypto import encrypt_sensitive_config

        raw_config = {"ig_page_id": body.ig_page_id, "page_access_token": body.page_access_token}
        encrypted_config = encrypt_sensitive_config(raw_config)

        if channel:
            channel.config = encrypted_config
            channel.is_active = True
        else:
            channel = Channel(
                workspace_id=current.workspace_id,
                type="instagram",
                name="Instagram DM",
                is_active=True,
                config=encrypted_config,
            )
            db.add(channel)

    return {"configured": True, "channel_type": "instagram", "page_id": body.ig_page_id}


# ─── Channels Status ──────────────────────────────────────────────────────────

@router.get("/channels")
@limiter.limit(settings.default_rate_limit)
async def list_channels(
    request: Request,
    current: Annotated[CurrentUser, Depends(require_reviewer)],
):
    """List all configured channels for this workspace (tokens masked)."""
    from radd.db.models import Channel
    async with get_db_session(current.workspace_id) as db:
        result = await db.execute(
            select(Channel).where(Channel.workspace_id == current.workspace_id)
        )
        channels = result.scalars().all()

    return {
        "channels": [
            {
                "id": str(ch.id),
                "type": ch.type,
                "name": ch.name,
                "is_active": ch.is_active,
                "config": {
                    k: "***" if "token" in k.lower() or "secret" in k.lower() else v
                    for k, v in (ch.config or {}).items()
                },
                "created_at": ch.created_at.isoformat() if ch.created_at else "",
            }
            for ch in channels
        ]
    }
