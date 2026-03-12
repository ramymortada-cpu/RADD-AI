"""
Seed development data:
  • 1 workspace, 1 owner, 1 agent, 1 reviewer
  • 1 WhatsApp channel
  • 5 sample customers with different tiers (new, standard, returning, vip, at_risk)
  • 5 sample KB documents (FAQ)

Run with: make seed
"""
import asyncio
import hashlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from radd.auth.service import hash_password
from radd.db.base import AsyncSessionLocal, engine
from radd.db.models import Base, Channel, Customer, KBDocument, User, Workspace


async def seed():
    print("Seeding development data...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Skip if already seeded
        result = await db.execute(text("SELECT COUNT(*) FROM workspaces"))
        if result.scalar() > 0:
            print("Database already seeded. Skipping.")
            return

        # ── Workspace ─────────────────────────────────────────────────────────
        workspace = Workspace(
            name="Demo Store — متجر تجريبي",
            slug="demo-store",
            settings={
                "confidence_auto_threshold": 0.85,
                "confidence_soft_escalation_threshold": 0.60,
                "business_hours": {
                    "start": "09:00",
                    "end": "22:00",
                    "timezone": "Asia/Riyadh",
                },
                "store_name": "متجر التجريبي",
                "owner_phone": "",  # Fill with real WhatsApp number to receive briefings
                "wa_phone_number_id": "",
            },
            plan="pilot",
            status="active",
        )
        db.add(workspace)
        await db.flush()

        wid = workspace.id

        # ── RLS context (use string interpolation — SET LOCAL doesn't support $1) ─
        await db.execute(
            text(f"SET LOCAL app.current_workspace_id = '{wid}'")
        )

        # ── Users ─────────────────────────────────────────────────────────────
        owner = User(
            workspace_id=wid,
            email="owner@demo-store.sa",
            password_hash=hash_password("demo_owner_2026"),
            name="مدير المتجر",
            role="owner",
            is_active=True,
        )
        agent = User(
            workspace_id=wid,
            email="agent@demo-store.sa",
            password_hash=hash_password("demo_agent_2026"),
            name="موظف خدمة العملاء",
            role="agent",
            is_active=True,
        )
        reviewer = User(
            workspace_id=wid,
            email="reviewer@demo-store.sa",
            password_hash=hash_password("demo_reviewer_2026"),
            name="مراجع المحتوى",
            role="reviewer",
            is_active=True,
        )
        db.add_all([owner, agent, reviewer])
        await db.flush()  # get owner.id for KB docs

        # ── WhatsApp channel ──────────────────────────────────────────────────
        channel = Channel(
            workspace_id=wid,
            type="whatsapp",
            name="واتساب الرئيسي",
            is_active=True,
            config={
                "wa_phone_number_id": "",
                "wa_business_account_id": "",
                "wa_api_token_ref": "env:WA_API_TOKEN",
            },
        )
        db.add(channel)

        # ── Sample customers (5 tiers) ────────────────────────────────────────
        now = datetime.now(timezone.utc)

        sample_customers = [
            {
                "phone": "+966501000001",
                "display_name": "عميل جديد",
                "total_conversations": 0,
                "total_escalations": 0,
                "customer_tier": "new",
                "avg_sentiment": None,
                "salla_total_orders": 0,
                "salla_total_revenue": 0,
                "last_complaint_at": None,
            },
            {
                "phone": "+966501000002",
                "display_name": "عميل عادي",
                "total_conversations": 2,
                "total_escalations": 0,
                "customer_tier": "standard",
                "avg_sentiment": 0.65,
                "salla_total_orders": 2,
                "salla_total_revenue": 450.00,
                "last_complaint_at": None,
            },
            {
                "phone": "+966501000003",
                "display_name": "عميل متكرر",
                "total_conversations": 7,
                "total_escalations": 1,
                "customer_tier": "returning",
                "avg_sentiment": 0.72,
                "salla_total_orders": 5,
                "salla_total_revenue": 1850.00,
                "last_complaint_at": now - timedelta(days=20),
            },
            {
                "phone": "+966501000004",
                "display_name": "عميل VIP — أبو فهد",
                "total_conversations": 18,
                "total_escalations": 1,
                "customer_tier": "vip",
                "avg_sentiment": 0.88,
                "salla_total_orders": 14,
                "salla_total_revenue": 7200.00,
                "last_complaint_at": None,
            },
            {
                "phone": "+966501000005",
                "display_name": "عميل غير راضٍ",
                "total_conversations": 5,
                "total_escalations": 4,
                "customer_tier": "at_risk",
                "avg_sentiment": 0.20,
                "salla_total_orders": 3,
                "salla_total_revenue": 890.00,
                "last_complaint_at": now - timedelta(days=3),
            },
        ]

        for c in sample_customers:
            phone_hash = hashlib.sha256(c["phone"].encode()).hexdigest()
            customer = Customer(
                workspace_id=wid,
                channel_identifier_hash=phone_hash,
                channel_type="whatsapp",
                display_name=c["display_name"],
                total_conversations=c["total_conversations"],
                total_escalations=c["total_escalations"],
                customer_tier=c["customer_tier"],
                avg_sentiment=c["avg_sentiment"],
                salla_total_orders=c["salla_total_orders"],
                salla_total_revenue=c["salla_total_revenue"],
                last_complaint_at=c["last_complaint_at"],
                last_seen_at=now - timedelta(days=1),
            )
            db.add(customer)

        # ── Sample KB documents (5 FAQs) ──────────────────────────────────────
        kb_docs = [
            {
                "title": "سياسة الإرجاع والاستبدال",
                "content": (
                    "يمكن إرجاع أي منتج خلال 14 يوماً من تاريخ الاستلام بشرط أن يكون المنتج في حالته الأصلية "
                    "وغير مستخدم وفي عبوته الأصلية. لإتمام الإرجاع، تواصل معنا عبر واتساب وأرسل صورة المنتج "
                    "ورقم الطلب. سيتم استرداد المبلغ خلال 5-7 أيام عمل."
                ),
                "content_type": "text/plain",
                "status": "approved",
                "version": 1,
            },
            {
                "title": "مواعيد التوصيل والشحن",
                "content": (
                    "نوفر الشحن لجميع مناطق المملكة العربية السعودية. التوصيل داخل الرياض: 1-2 يوم عمل. "
                    "المناطق الأخرى: 2-4 أيام عمل. الشحن السريع متاح بتكلفة إضافية 20 ر.س ويصل خلال 24 ساعة. "
                    "يمكن تتبع طلبك عبر الرابط المرسل في رسالة تأكيد الطلب."
                ),
                "content_type": "text/plain",
                "status": "approved",
                "version": 1,
            },
            {
                "title": "طرق الدفع المتاحة",
                "content": (
                    "نقبل جميع طرق الدفع التالية: الدفع عند الاستلام (COD)، بطاقات الائتمان والخصم (Visa, Mastercard), "
                    "Apple Pay، STC Pay، مدى. جميع المدفوعات آمنة ومشفرة. لا نحتفظ ببيانات بطاقتك الائتمانية."
                ),
                "content_type": "text/plain",
                "status": "approved",
                "version": 1,
            },
            {
                "title": "مواعيد عمل خدمة العملاء",
                "content": (
                    "فريق خدمة العملاء متاح من الأحد إلى الخميس من الساعة 9 صباحاً حتى 10 مساءً. "
                    "أيام الجمعة والسبت: من 2 ظهراً حتى 10 مساءً. "
                    "في الأوقات خارج الدوام، رَدّ (المساعد الذكي) سيساعدك وسيُحوّل طلبك للفريق صباح يوم العمل التالي."
                ),
                "content_type": "text/plain",
                "status": "approved",
                "version": 1,
            },
            {
                "title": "الأسئلة الشائعة — الطلبات والتتبع",
                "content": (
                    "س: كيف أتابع طلبي؟ \nج: أرسل رقم طلبك وسنراجع حالته فوراً.\n\n"
                    "س: هل يمكن تعديل الطلب بعد تأكيده؟ \nج: يمكن تعديل الطلب خلال ساعة من الطلب فقط.\n\n"
                    "س: ماذا أفعل إذا وصل المنتج تالفاً؟ \nج: أرسل صورة للمنتج التالف ورقم الطلب وسنعالج الأمر فوراً.\n\n"
                    "س: هل يمكن إلغاء الطلب؟ \nج: يمكن إلغاء الطلب قبل الشحن فقط. بعد الشحن تُطبّق سياسة الإرجاع."
                ),
                "content_type": "text/plain",
                "status": "approved",
                "version": 1,
            },
        ]

        for doc in kb_docs:
            db.add(
                KBDocument(
                    workspace_id=wid,
                    title=doc["title"],
                    content=doc["content"],
                    content_type=doc["content_type"],
                    status=doc["status"],
                    version=doc["version"],
                    uploaded_by_user_id=owner.id,
                    approved_by_user_id=owner.id,
                )
            )

        await db.commit()

    print("✅ Seeded successfully!")
    print()
    print("  Workspace:  Demo Store (slug: demo-store)")
    print("  Owner:      owner@demo-store.sa  / demo_owner_2026")
    print("  Agent:      agent@demo-store.sa  / demo_agent_2026")
    print("  Reviewer:   reviewer@demo-store.sa / demo_reviewer_2026")
    print()
    print("  Customers:  5 customers (new / standard / returning / vip / at_risk)")
    print("  KB Docs:    5 approved Arabic FAQ documents")
    print()
    print("  API docs:   http://localhost:8000/docs")
    print("  Health:     http://localhost:8000/health")
    print("  Dashboard:  http://localhost:3000")


if __name__ == "__main__":
    asyncio.run(seed())
