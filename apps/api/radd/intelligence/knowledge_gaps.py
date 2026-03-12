"""RADD AI — Knowledge Gap Intelligence"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class KnowledgeGap:
    question_pattern: str; sample_question: str; occurrence_count: int; intent: str; last_asked: datetime; workspace_id: str

async def get_knowledge_gaps(db_session, workspace_id: str, days: int = 7, limit: int = 20) -> list[KnowledgeGap]:
    from sqlalchemy import text
    q = text("""SELECT m.content_normalized AS sq, c.intent, COUNT(*) AS cnt, MAX(m.created_at) AS la
        FROM messages m JOIN conversations c ON m.conversation_id = c.id
        WHERE m.sender_type = 'customer' AND c.workspace_id = :wid
        AND c.resolution_type IN ('escalated_hard','escalated_soft')
        AND m.created_at > NOW() - INTERVAL :di
        GROUP BY m.content_normalized, c.intent HAVING COUNT(*) >= 2
        ORDER BY cnt DESC LIMIT :lim""")
    result = await db_session.execute(q, {"wid": workspace_id, "di": f"{days} days", "lim": limit})
    return [KnowledgeGap(r.sq[:50], r.sq, r.cnt, r.intent or "general", r.la, workspace_id) for r in result.fetchall()]

async def get_gap_summary(db_session, workspace_id: str) -> Optional[str]:
    gaps = await get_knowledge_gaps(db_session, workspace_id, 7, 5)
    if not gaps: return None
    total = sum(g.occurrence_count for g in gaps)
    lines = [f"📚 فجوات المعرفة هالأسبوع ({total} سؤال بدون جواب):", ""]
    for i, g in enumerate(gaps, 1): lines.append(f'{i}. "{g.sample_question[:40]}..." ({g.occurrence_count} مرة)')
    lines.extend(["", "سد هالفجوات في لوحة التحكم وأدائي يتحسن 📈"])
    return "\n".join(lines)
