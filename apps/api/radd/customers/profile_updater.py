"""RADD AI — Customer Profile Updater + Context Builder"""
from datetime import datetime

POSITIVE = {"شكرا","شكراً","ممتاز","حلو","الله يعطيك العافية","تسلم","رائع","ممنون","جميل","احسنت","مشكور","تمام"}
NEGATIVE = {"زعلان","خربان","سيء","اسوأ","ما يشتغل","مشكلة","شكوى","بشتكي","بنشر تقييم","غش","نصب","كذب","متاخر","تاخير","ما وصل","مكسور","غلط"}

def compute_sentiment(text: str) -> float:
    if not text: return 0.5
    words = set(text.split())
    p, n = len(words & POSITIVE), len(words & NEGATIVE)
    if p > n: return min(1.0, 0.6 + p*0.1)
    if n > p: return max(0.0, 0.4 - n*0.1)
    return 0.5

def compute_tier(customer) -> str:
    if customer.total_escalations and customer.total_escalations >= 3:
        if customer.last_complaint_at:
            if (datetime.utcnow() - customer.last_complaint_at).days <= 30:
                return "at_risk"
    if customer.total_conversations and customer.total_conversations > 10: return "vip"
    if customer.salla_total_revenue and float(customer.salla_total_revenue) > 5000: return "vip"
    if customer.total_conversations and customer.total_conversations >= 4: return "returning"
    if customer.total_conversations and customer.total_conversations >= 1: return "standard"
    return "new"

def update_profile(customer, conversation, msg_text: str):
    customer.total_conversations = (customer.total_conversations or 0) + 1
    customer.last_seen_at = datetime.utcnow()
    if conversation.resolution_type in ("escalated_hard","escalated_soft"):
        customer.total_escalations = (customer.total_escalations or 0) + 1
        customer.last_complaint_at = datetime.utcnow()
    s = compute_sentiment(msg_text)
    customer.avg_sentiment = round(float(customer.avg_sentiment or 0.5)*0.7 + s*0.3, 2)
    customer.customer_tier = compute_tier(customer)
    return customer

def build_customer_context(customer) -> str:
    if not customer or not customer.total_conversations: return "هذا عميل جديد. رحّب به بودّ."
    parts = [f"العميل تواصل {customer.total_conversations} مرة سابقاً."]
    if customer.display_name: parts[0] += f" اسمه: {customer.display_name}"
    tier_msg = {"vip":"⭐ عميل VIP — عامله بتقدير.","at_risk":"⚠️ عميل غير راضٍ — كن حذراً وودوداً.","returning":"عميل متكرر — كن مباشراً.","new":"عميل جديد — رحّب به."}
    t = customer.customer_tier or "standard"
    if t in tier_msg: parts.append(tier_msg[t])
    if customer.last_complaint_at:
        d = (datetime.utcnow() - customer.last_complaint_at).days
        if d <= 7: parts.append(f"اشتكى قبل {d} أيام.")
    if customer.salla_total_orders and customer.salla_total_orders > 0:
        parts.append(f"إجمالي طلباته: {customer.salla_total_orders}")
    return "\n".join(parts)
