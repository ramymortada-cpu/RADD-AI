"""RADD AI — Morning Briefing Engine"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

INTENT_AR = {"greeting":"تحية","order_status":"حالة الطلب","shipping":"الشحن","return_policy":"الإرجاع","store_hours":"مواعيد العمل","product_inquiry":"استفسار عن منتج","product_comparison":"مقارنة منتجات","purchase_hesitation":"تردد في الشراء","general":"استفسار عام"}

@dataclass
class Briefing:
    workspace_name: str; total: int; auto: int; escalated: int; rate: float; blocks: int; top_intent: str; top_count: int; gaps: int; hours_saved: float

async def generate_briefing(db_session, wid: str, name: str) -> Optional[Briefing]:
    from sqlalchemy import text
    ys = datetime.utcnow().replace(hour=0,minute=0,second=0) - timedelta(days=1)
    ye = ys + timedelta(days=1)
    r = await db_session.execute(text("SELECT COUNT(*) t, COUNT(*) FILTER(WHERE resolution_type IN ('auto_template','auto_rag')) a, COUNT(*) FILTER(WHERE resolution_type IN ('escalated_hard','escalated_soft')) e FROM conversations WHERE workspace_id=:w AND created_at>=:s AND created_at<:e"),{"w":wid,"s":ys,"e":ye})
    row = r.fetchone()
    if not row or row.t == 0: return None
    bl = (await db_session.execute(text("SELECT COUNT(*) b FROM escalation_events WHERE workspace_id=:w AND created_at>=:s AND created_at<:e"),{"w":wid,"s":ys,"e":ye})).fetchone().b or 0
    ir = (await db_session.execute(text("SELECT intent,COUNT(*) c FROM conversations WHERE workspace_id=:w AND created_at>=:s AND created_at<:e AND intent IS NOT NULL GROUP BY intent ORDER BY c DESC LIMIT 1"),{"w":wid,"s":ys,"e":ye})).fetchone()
    gr = (await db_session.execute(text("SELECT COUNT(DISTINCT m.content_normalized) g FROM messages m JOIN conversations c ON m.conversation_id=c.id WHERE c.workspace_id=:w AND c.resolution_type IN ('escalated_hard','escalated_soft') AND m.sender_type='customer' AND m.created_at>=NOW()-INTERVAL '7 days'"),{"w":wid})).fetchone().g or 0
    return Briefing(name, row.t, row.a, row.e, round(row.a/row.t*100,1), bl, ir.intent if ir else "general", ir.c if ir else 0, gr, round(row.a*2/60,1))

def format_briefing(b: Briefing) -> str:
    i = INTENT_AR.get(b.top_intent, b.top_intent)
    m = f"""صباح الخير يا {b.workspace_name} ☀️\n\nأمس تعاملت مع {b.total} محادثة:\n✅ {b.auto} حليتها لحالي ({b.rate}%)\n👤 {b.escalated} حولتها لفريقك\n🛡️ منعت {b.blocks} رد غير دقيق\n\nأكثر سؤال: "{i}" ({b.top_count} مرة)"""
    if b.gaps > 0: m += f"\n⚠️ {b.gaps} فجوات معرفة جديدة — سدها في لوحة التحكم"
    if b.hours_saved > 0: m += f"\n\n⏱️ وفرت عليك تقريباً {b.hours_saved} ساعات عمل"
    return m + "\n\n— رَدّ"
