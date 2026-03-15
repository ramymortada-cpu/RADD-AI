from contextlib import asynccontextmanager

import sentry_sdk
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from radd.admin.cod_shield_router import router as cod_shield_router
from radd.admin.revenue_dashboard_router import router as revenue_dashboard_router
from radd.admin.router import router as admin_router
from radd.admin.v4_router import router as admin_v4_router
from radd.auth.router import router as auth_router
from radd.channels.instagram_router import router as instagram_router
from radd.channels.zid_router import router as zid_router
from radd.alerts import init_alert_manager
from radd.config import settings
from radd.monitoring.alerts import init_alert_manager as init_slack_alert_manager
from radd.conversations.router import router as conversations_router
from radd.deps import check_db_health, check_qdrant_health, check_redis_health
from radd.developer.router import router as developer_router
from radd.escalation.router import router as escalations_router
from radd.intelligence.router import router as intelligence_router
from radd.knowledge.router import router as kb_router
from radd.limiter import limiter
from radd.monitoring.sentry_and_logging import _filter_pii
from radd.superadmin.router import router as superadmin_router
from radd.webhooks.router import router as webhooks_router
from radd.webhooks.shipping_router import router as shipping_router
from radd.webhooks.cart_router import router as cart_router
from radd.webhooks.twilio_router import router as twilio_router
from radd.websocket.router import router as ws_router

logger = structlog.get_logger()

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        traces_sample_rate=0.1,
        profiles_sample_rate=0.1,
        release=f"radd-api@{settings.app_version}",
        before_send=_filter_pii,
        send_default_pii=False,
    )

init_alert_manager(
    slack_webhook_url=settings.slack_alert_webhook_url,
    app_env=settings.app_env,
)

# Initialize Slack alerts for pipeline (monitoring.alerts)
_slack_webhook = settings.slack_alert_webhook or settings.slack_alert_webhook_url
if _slack_webhook:
    init_slack_alert_manager(_slack_webhook)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("radd.startup", env=settings.app_env, version=settings.app_version)
    yield
    logger.info("radd.shutdown")


app = FastAPI(
    title="Radd API",
    description="Arabic-first customer service automation for Saudi e-commerce",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_cors_origins = (
    ["*"] if settings.debug
    else settings.cors_origins
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")
app.include_router(twilio_router, prefix="/api/v1")
app.include_router(cart_router, prefix="/api/v1")
app.include_router(shipping_router)
app.include_router(kb_router, prefix="/api/v1")
app.include_router(conversations_router, prefix="/api/v1")
app.include_router(escalations_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(cod_shield_router, prefix="/api/v1")
app.include_router(revenue_dashboard_router, prefix="/api/v1")
app.include_router(superadmin_router, prefix="/api/v1")
app.include_router(intelligence_router, prefix="/api/v1")
app.include_router(instagram_router, prefix="/api/v1")
app.include_router(zid_router, prefix="/api/v1")
app.include_router(developer_router, prefix="/api/v1")
app.include_router(admin_v4_router, prefix="/api/v1")
app.include_router(ws_router)  # WebSocket — no /api/v1 prefix


# ─── Health endpoints ─────────────────────────────────────────────────────────
@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "version": settings.app_version}


@app.get("/ready", tags=["health"])
async def readiness():
    db_ok = await check_db_health()
    redis_ok = await check_redis_health()
    qdrant_ok = await check_qdrant_health()

    all_ok = db_ok and redis_ok and qdrant_ok
    return {
        "status": "ready" if all_ok else "degraded",
        "checks": {
            "database": "ok" if db_ok else "fail",
            "redis": "ok" if redis_ok else "fail",
            "qdrant": "ok" if qdrant_ok else "fail",
        },
    }
