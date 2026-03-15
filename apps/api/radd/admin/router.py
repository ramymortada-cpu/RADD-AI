"""
Admin router — aggregates sub-routers for maintainability.
Split from original 900+ line file into: analytics, customers, settings, rules, integrations.
"""
from __future__ import annotations

from fastapi import APIRouter

from radd.admin.analytics_router import router as analytics_router
from radd.admin.control_center_router import (
    control_router,
    kb_manage_router,
    templates_router,
)
from radd.admin.customers_router import router as customers_router
from radd.admin.integrations_router import router as integrations_router
from radd.admin.rules_router import router as rules_router
from radd.admin.settings_router import router as settings_router

router = APIRouter(prefix="/admin", tags=["Admin"])

router.include_router(analytics_router, prefix="")
router.include_router(control_router, prefix="")
router.include_router(kb_manage_router, prefix="")
router.include_router(templates_router, prefix="")
router.include_router(customers_router, prefix="")
router.include_router(settings_router, prefix="")
router.include_router(rules_router, prefix="")
router.include_router(integrations_router, prefix="")
