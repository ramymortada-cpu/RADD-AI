from __future__ import annotations
"""
RADD Score — 0-100 composite score for store CS performance.
Measures how well RADD is serving customers for this workspace.

Formula:
  Automation Rate    × 30 pts  (auto-resolved / total)
  Response Quality   × 25 pts  (avg confidence of auto responses)
  Escalation Health  × 20 pts  (low escalation rate = better)
  Knowledge Coverage × 15 pts  (low "no KB" rate = better)
  Customer Happiness × 10 pts  (avg sentiment of customers)
"""
from dataclasses import dataclass
import structlog

logger = structlog.get_logger()


@dataclass
class RaddScore:
    total: int                    # 0-100
    automation_score: int         # 0-30
    quality_score: int            # 0-25
    escalation_score: int         # 0-20
    knowledge_score: int          # 0-15
    happiness_score: int          # 0-10
    grade: str                    # A+ / A / B / C / D
    summary_ar: str


async def calculate_radd_score(
    db_session,
    workspace_id: str,
    period_days: int = 30,
) -> RaddScore:
    """
    Calculate the RADD Score for a workspace over the last N days.
    """
    from sqlalchemy import text

    try:
        result = await db_session.execute(
            text(f"""
                SELECT
                    COUNT(*) as total_convs,
                    COUNT(*) FILTER(WHERE resolution_type IN ('auto_template', 'auto_rag')) as auto_convs,
                    COUNT(*) FILTER(WHERE resolution_type LIKE 'escalated%%') as escalated_convs,
                    AVG(confidence_score) FILTER(WHERE resolution_type IN ('auto_template', 'auto_rag')) as avg_auto_confidence,
                    COUNT(*) FILTER(WHERE confidence_score < 0.2 AND resolution_type LIKE 'escalated%%') as no_kb_convs
                FROM conversations
                WHERE workspace_id = :wid
                  AND created_at >= NOW() - INTERVAL '{period_days} days'
            """),
            {"wid": workspace_id},
        )
        conv_row = result.fetchone()

        # Customer sentiment
        sent_result = await db_session.execute(
            text("""
                SELECT AVG(avg_sentiment) as avg_sent
                FROM customers
                WHERE workspace_id = :wid
                  AND avg_sentiment IS NOT NULL
            """),
            {"wid": workspace_id},
        )
        sent_row = sent_result.fetchone()

    except Exception as e:
        logger.error("radd_score.db_failed", error=str(e))
        return _default_score()

    total_convs = conv_row.total_convs or 0
    if total_convs == 0:
        return _default_score()

    auto_convs = conv_row.auto_convs or 0
    escalated_convs = conv_row.escalated_convs or 0
    avg_confidence = float(conv_row.avg_auto_confidence or 0)
    no_kb_convs = conv_row.no_kb_convs or 0
    avg_sentiment = float(sent_row.avg_sent or 0.5) if sent_row else 0.5

    # ── Automation Rate (0-30) ──────────────────────────────────────────────
    automation_rate = auto_convs / total_convs
    automation_score = min(30, int(automation_rate * 30 / 0.75))  # 75% = full marks

    # ── Quality Score (0-25) ───────────────────────────────────────────────
    quality_score = min(25, int(avg_confidence * 25 / 0.85))  # 0.85 confidence = full

    # ── Escalation Health (0-20) ────────────────────────────────────────────
    escalation_rate = escalated_convs / total_convs
    escalation_score = max(0, int((1 - escalation_rate / 0.40) * 20))  # 40% escalation = 0

    # ── Knowledge Coverage (0-15) ───────────────────────────────────────────
    no_kb_rate = no_kb_convs / total_convs
    knowledge_score = max(0, int((1 - no_kb_rate / 0.20) * 15))  # 20% no-KB = 0

    # ── Customer Happiness (0-10) ───────────────────────────────────────────
    happiness_score = min(10, int((avg_sentiment - 0.3) / 0.7 * 10))

    total = automation_score + quality_score + escalation_score + knowledge_score + happiness_score
    total = max(0, min(100, total))

    grade = _grade(total)
    summary_ar = _summary_arabic(total, automation_rate, escalation_rate, avg_confidence)

    logger.info("radd_score.calculated", workspace_id=workspace_id, score=total, grade=grade)

    return RaddScore(
        total=total,
        automation_score=automation_score,
        quality_score=quality_score,
        escalation_score=escalation_score,
        knowledge_score=knowledge_score,
        happiness_score=happiness_score,
        grade=grade,
        summary_ar=summary_ar,
    )


def _grade(score: int) -> str:
    if score >= 90: return "A+"
    if score >= 80: return "A"
    if score >= 70: return "B"
    if score >= 60: return "C"
    if score >= 50: return "D"
    return "F"


def _summary_arabic(score: int, auto_rate: float, esc_rate: float, confidence: float) -> str:
    if score >= 85:
        return f"أداء ممتاز! رَدّ يتعامل مع {auto_rate:.0%} من المحادثات تلقائياً بثقة عالية."
    if score >= 70:
        return f"أداء جيد. معدل الأتمتة {auto_rate:.0%}. هناك فرصة لتحسين قاعدة المعرفة."
    if score >= 50:
        return f"أداء متوسط. معدل التصعيد {esc_rate:.0%} مرتفع. أضف محتوى لقاعدة المعرفة."
    return f"يحتاج تحسين عاجل. قاعدة المعرفة تحتاج محتوى أكثر لتغطية استفسارات عملائك."


def _default_score() -> RaddScore:
    return RaddScore(
        total=0, automation_score=0, quality_score=0,
        escalation_score=0, knowledge_score=0, happiness_score=0,
        grade="N/A", summary_ar="لا توجد بيانات كافية بعد. سيظهر التقييم بعد أول 10 محادثات.",
    )
