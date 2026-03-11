from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from radd.auth.router import router as auth_router
from radd.admin.router import router as admin_router
from radd.conversations.router import router as conversations_router
from radd.escalation.router import router as escalations_router
from radd.knowledge.router import router as kb_router
from radd.webhooks.router import router as webhooks_router
from radd.websocket.router import router as ws_router
from radd.config import settings
from radd.deps import check_db_health, check_qdrant_health, check_redis_health

logger = structlog.get_logger()


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")
app.include_router(kb_router, prefix="/api/v1")
app.include_router(conversations_router, prefix="/api/v1")
app.include_router(escalations_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
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
