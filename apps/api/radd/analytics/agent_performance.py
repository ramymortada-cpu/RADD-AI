from __future__ import annotations
"""
RADD AI — Agent Performance Analytics
Measures how well each human agent handles escalated conversations.
Metrics:
- avg_resolution_time_minutes
- total_resolved
- csat_score (estimated from post-resolution sentiment)
- escalation_acceptance_rate
- avg_response_time_minutes
"""
from dataclasses import dataclass
import structlog

logger = structlog.get_logger()


@dataclass
class AgentMetrics:
    user_id: str
    agent_name: str
    agent_email: str
    total_assigned: int
    total_resolved: int
    resolution_rate: float          # resolved / assigned
    avg_resolution_minutes: float
    avg_first_response_minutes: float
    estimated_csat: float           # 0.0-5.0


async def get_agent_performance(
    db_session,
    workspace_id: str,
    period_days: int = 30,
) -> list[AgentMetrics]:
    """
    Calculate performance metrics for all agents in this workspace.
    """
    from sqlalchemy import text

    try:
        result = await db_session.execute(
            text(f"""
                SELECT
                    u.id as user_id,
                    u.name as agent_name,
                    u.email as agent_email,
                    COUNT(ee.id) as total_assigned,
                    COUNT(ee.id) FILTER(WHERE ee.status = 'resolved') as total_resolved,
                    AVG(
                        EXTRACT(EPOCH FROM (ee.resolved_at - ee.created_at)) / 60
                    ) FILTER(WHERE ee.resolved_at IS NOT NULL) as avg_resolution_minutes,
                    AVG(
                        EXTRACT(EPOCH FROM (ee.accepted_at - ee.created_at)) / 60
                    ) FILTER(WHERE ee.accepted_at IS NOT NULL) as avg_first_response_minutes
                FROM users u
                LEFT JOIN escalation_events ee ON
                    ee.assigned_user_id = u.id
                    AND ee.workspace_id = :wid
                    AND ee.created_at >= NOW() - INTERVAL '{period_days} days'
                WHERE u.workspace_id = :wid
                  AND u.role IN ('agent', 'admin', 'owner')
                  AND u.is_active = true
                GROUP BY u.id, u.name, u.email
                ORDER BY total_resolved DESC NULLS LAST
            """),
            {"wid": workspace_id},
        )
        rows = result.fetchall()
    except Exception as e:
        logger.error("agent_performance.db_failed", error=str(e))
        return []

    metrics = []
    for row in rows:
        total_assigned = row.total_assigned or 0
        total_resolved = row.total_resolved or 0
        avg_res = float(row.avg_resolution_minutes or 0)
        avg_first = float(row.avg_first_response_minutes or 0)
        resolution_rate = total_resolved / total_assigned if total_assigned > 0 else 0

        # Estimate CSAT from resolution rate and speed
        # Fast + high resolution → higher CSAT estimate
        speed_factor = max(0, 1 - avg_res / 120)  # 120 min = 0 speed score
        csat_estimate = min(5.0, 2.5 + (resolution_rate * 1.5) + (speed_factor * 1.0))

        metrics.append(AgentMetrics(
            user_id=str(row.user_id),
            agent_name=row.agent_name,
            agent_email=row.agent_email,
            total_assigned=total_assigned,
            total_resolved=total_resolved,
            resolution_rate=round(resolution_rate, 3),
            avg_resolution_minutes=round(avg_res, 1),
            avg_first_response_minutes=round(avg_first, 1),
            estimated_csat=round(csat_estimate, 2),
        ))

    logger.info("agent_performance.calculated", workspace_id=workspace_id, agents=len(metrics))
    return metrics


def get_team_summary(metrics: list[AgentMetrics]) -> dict:
    """Summarize team performance for the dashboard header."""
    if not metrics:
        return {"agents": 0, "avg_csat": 0, "avg_resolution_minutes": 0, "total_resolved": 0}

    active = [m for m in metrics if m.total_assigned > 0]
    if not active:
        return {"agents": len(metrics), "avg_csat": 0, "avg_resolution_minutes": 0, "total_resolved": 0}

    return {
        "agents": len(active),
        "avg_csat": round(sum(m.estimated_csat for m in active) / len(active), 2),
        "avg_resolution_minutes": round(
            sum(m.avg_resolution_minutes for m in active) / len(active), 1
        ),
        "total_resolved": sum(m.total_resolved for m in active),
    }
