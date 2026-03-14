from __future__ import annotations
"""
RADD AI — Cross-Merchant Intelligence
Anonymized benchmarks across workspaces by sector.
"automation rate لمتاجر العطور المماثلة: 72%. أنت عند 58%."
All data is fully anonymized — no workspace names or IDs shared.
"""
from dataclasses import asdict, dataclass
import json
import structlog

logger = structlog.get_logger()


@dataclass
class SectorBenchmark:
    sector: str
    sector_ar: str
    peer_count: int                # Number of peers in this sector (anonymized)
    avg_automation_rate: float     # 0-1
    avg_escalation_rate: float     # 0-1
    avg_csat: float                # 0-5
    avg_response_confidence: float # 0-1
    top_intents: list[str]         # Most common intents in this sector


@dataclass
class MerchantBenchmarkReport:
    workspace_id: str
    sector: str
    my_automation_rate: float
    my_escalation_rate: float
    sector_avg_automation: float
    sector_avg_escalation: float
    peer_count: int
    percentile: int                 # 0-100 where merchant ranks
    gap_analysis: list[dict]        # [{"metric": ..., "yours": ..., "benchmark": ..., "gap": ...}]
    recommendations: list[str]


SECTOR_AR = {
    "perfumes": "العطور والتجميل",
    "fashion": "الأزياء والملابس",
    "electronics": "الإلكترونيات",
    "food": "الأغذية والمشروبات",
    "jewelry": "المجوهرات والإكسسوارات",
    "other": "أخرى",
}


BENCHMARK_CACHE_TTL = 3600  # 1 hour


async def get_sector_benchmarks(
    db_session,
    sector: str | None = None,
) -> list[SectorBenchmark]:
    """
    Compute anonymized benchmarks grouped by sector.
    Cached in Redis for 1 hour to avoid heavy aggregates on every request.
    """
    from sqlalchemy import text
    from radd.deps import get_redis

    cache_key = f"benchmark:sector:{sector or 'all'}"
    r = get_redis()
    try:
        cached = await r.get(cache_key)
        if cached:
            data = json.loads(cached)
            return [SectorBenchmark(**d) for d in data]
    except Exception:
        pass

    sector_filter = "AND w.sector = :sector" if sector else ""
    params: dict = {}
    if sector:
        params["sector"] = sector

    try:
        result = await db_session.execute(
            text(f"""
                SELECT
                    COALESCE(w.sector, 'other') as sector,
                    COUNT(DISTINCT w.id) as peer_count,
                    AVG(conv_stats.automation_rate) as avg_auto,
                    AVG(conv_stats.escalation_rate) as avg_esc,
                    AVG(conv_stats.avg_confidence) as avg_conf
                FROM workspaces w
                LEFT JOIN LATERAL (
                    SELECT
                        COALESCE(
                            COUNT(*) FILTER(WHERE c.resolution_type IN ('auto_template','auto_rag'))::float
                            / NULLIF(COUNT(*), 0), 0
                        ) as automation_rate,
                        COALESCE(
                            COUNT(*) FILTER(WHERE c.resolution_type LIKE 'escalated%%')::float
                            / NULLIF(COUNT(*), 0), 0
                        ) as escalation_rate,
                        AVG(c.confidence_score) as avg_confidence
                    FROM conversations c
                    WHERE c.workspace_id = w.id
                      AND c.created_at >= NOW() - INTERVAL '30 days'
                ) conv_stats ON true
                WHERE w.status = 'active'
                  AND w.plan != 'pilot'
                  {sector_filter}
                GROUP BY COALESCE(w.sector, 'other')
                HAVING COUNT(DISTINCT w.id) >= 3
                ORDER BY peer_count DESC
            """),
            params,
        )
        rows = result.fetchall()
    except Exception as e:
        logger.error("cross_merchant.benchmark_failed", error=str(e))
        return []

    benchmarks = []
    for row in rows:
        benchmarks.append(SectorBenchmark(
            sector=row.sector,
            sector_ar=SECTOR_AR.get(row.sector, row.sector),
            peer_count=int(row.peer_count),
            avg_automation_rate=round(float(row.avg_auto or 0), 3),
            avg_escalation_rate=round(float(row.avg_esc or 0), 3),
            avg_csat=0.0,
            avg_response_confidence=round(float(row.avg_conf or 0), 3),
            top_intents=[],
        ))

    try:
        await r.set(cache_key, json.dumps([asdict(b) for b in benchmarks]), ex=BENCHMARK_CACHE_TTL)
    except Exception:
        pass

    return benchmarks


async def get_merchant_benchmark_report(
    db_session,
    workspace_id: str,
    period_days: int = 30,
) -> MerchantBenchmarkReport | None:
    """
    Compare this workspace against peers in the same sector.
    Cached in Redis for 1 hour.
    """
    from sqlalchemy import text
    from radd.utils.sql_helpers import safe_period_days
    from radd.deps import get_redis

    period_days = safe_period_days(period_days, min_val=7, max_val=90)
    cache_key = f"benchmark:workspace:{workspace_id}:{period_days}"
    r = get_redis()
    try:
        cached = await r.get(cache_key)
        if cached:
            d = json.loads(cached)
            return MerchantBenchmarkReport(**d)
    except Exception:
        pass

    # Get workspace sector
    try:
        ws_result = await db_session.execute(
            text("SELECT sector FROM workspaces WHERE id = :wid"),
            {"wid": workspace_id},
        )
        ws_row = ws_result.fetchone()
        sector = (ws_row.sector or "other") if ws_row else "other"
    except Exception:
        sector = "other"

    # My stats
    try:
        my_result = await db_session.execute(
            text(f"""
                SELECT
                    COALESCE(
                        COUNT(*) FILTER(WHERE resolution_type IN ('auto_template','auto_rag'))::float
                        / NULLIF(COUNT(*), 0), 0
                    ) as my_auto,
                    COALESCE(
                        COUNT(*) FILTER(WHERE resolution_type LIKE 'escalated%%')::float
                        / NULLIF(COUNT(*), 0), 0
                    ) as my_esc,
                    COUNT(*) as total
                FROM conversations
                WHERE workspace_id = :wid
                  AND created_at >= NOW() - INTERVAL '{period_days} days'
            """),
            {"wid": workspace_id},
        )
        my_row = my_result.fetchone()
        if not my_row or my_row.total == 0:
            return None

        my_auto = float(my_row.my_auto or 0)
        my_esc = float(my_row.my_esc or 0)
    except Exception as e:
        logger.error("cross_merchant.my_stats_failed", error=str(e))
        return None

    # Sector benchmarks
    benchmarks = await get_sector_benchmarks(db_session, sector)
    if not benchmarks:
        return None

    bm = benchmarks[0]

    # Percentile estimation
    if my_auto >= bm.avg_automation_rate:
        percentile = min(95, int(60 + (my_auto - bm.avg_automation_rate) / max(bm.avg_automation_rate, 0.01) * 30))
    else:
        percentile = max(5, int(60 - (bm.avg_automation_rate - my_auto) / max(bm.avg_automation_rate, 0.01) * 30))

    # Gap analysis
    gap_analysis = [
        {
            "metric": "معدل الأتمتة",
            "yours": round(my_auto * 100, 1),
            "benchmark": round(bm.avg_automation_rate * 100, 1),
            "gap": round((bm.avg_automation_rate - my_auto) * 100, 1),
            "unit": "%",
        },
        {
            "metric": "معدل التصعيد",
            "yours": round(my_esc * 100, 1),
            "benchmark": round(bm.avg_escalation_rate * 100, 1),
            "gap": round((my_esc - bm.avg_escalation_rate) * 100, 1),
            "unit": "%",
            "lower_is_better": True,
        },
    ]

    # Arabic recommendations
    recommendations = _build_recommendations(my_auto, my_esc, bm, sector)

    report = MerchantBenchmarkReport(
        workspace_id=workspace_id,
        sector=sector,
        my_automation_rate=round(my_auto * 100, 1),
        my_escalation_rate=round(my_esc * 100, 1),
        sector_avg_automation=round(bm.avg_automation_rate * 100, 1),
        sector_avg_escalation=round(bm.avg_escalation_rate * 100, 1),
        peer_count=bm.peer_count,
        percentile=percentile,
        gap_analysis=gap_analysis,
        recommendations=recommendations,
    )

    try:
        await r.set(cache_key, json.dumps(asdict(report)), ex=BENCHMARK_CACHE_TTL)
    except Exception:
        pass

    return report


def _build_recommendations(
    my_auto: float,
    my_esc: float,
    bm: SectorBenchmark,
    sector: str,
) -> list[str]:
    recs = []
    sector_ar = SECTOR_AR.get(sector, "قطاعك")

    auto_gap = bm.avg_automation_rate - my_auto
    esc_gap = my_esc - bm.avg_escalation_rate

    if auto_gap > 0.10:
        recs.append(
            f"معدل أتمتتك ({my_auto:.0%}) أقل من متوسط متاجر {sector_ar} ({bm.avg_automation_rate:.0%}). "
            f"أضف محتوى لقاعدة المعرفة يغطي الأسئلة الشائعة في قطاعك."
        )
    elif auto_gap < -0.05:
        recs.append(
            f"ممتاز! معدل أتمتتك ({my_auto:.0%}) أعلى من متوسط {sector_ar}. "
            f"أنت في المراتب الأولى لقطاعك."
        )

    if esc_gap > 0.05:
        recs.append(
            f"معدل تصعيدك ({my_esc:.0%}) أعلى من المتوسط ({bm.avg_escalation_rate:.0%}). "
            f"راجع نوع الأسئلة التي تُصعَّد وأضف إجاباتها في قاعدة المعرفة."
        )

    if not recs:
        recs.append(f"أداؤك قريب من متوسط متاجر {sector_ar}. استمر في تحسين قاعدة المعرفة.")

    return recs
