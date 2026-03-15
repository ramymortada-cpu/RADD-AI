"""
RADD AI — Salla Auto-Sync
Killer Feature #1: التاجر يربط سلة → رَدّ يعرف كل شيء تلقائياً
- يسحب كل المنتجات (اسم، سعر، وصف، صورة، توفر)
- يسحب سياسات المتجر
- يُنشئ KB documents تلقائياً
- يُحدّث تلقائياً عند تغيير المنتجات (webhook)
- يُزامن كل 6 ساعات (cron)
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger("radd.salla_sync")


@dataclass
class SallaProduct:
    id: str
    name: str
    price: float
    description: str
    currency: str = "SAR"
    sku: str | None = None
    in_stock: bool = True
    quantity: int | None = None
    images: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    sizes: list[str] = field(default_factory=list)
    colors: list[str] = field(default_factory=list)
    weight: float | None = None
    brand: str | None = None
    url: str | None = None


@dataclass
class SallaStoreInfo:
    name: str
    description: str
    return_policy: str | None = None
    shipping_policy: str | None = None
    exchange_policy: str | None = None
    working_hours: str | None = None
    contact_info: str | None = None
    payment_methods: list[str] = field(default_factory=list)
    shipping_companies: list[str] = field(default_factory=list)


@dataclass
class SyncResult:
    products_synced: int
    policies_synced: int
    kb_documents_created: int
    kb_documents_updated: int
    errors: list[str] = field(default_factory=list)
    sync_time: float = 0.0


# ──────────────────────────────────────────────
# Salla API Client
# ──────────────────────────────────────────────

class SallaAutoSync:
    """
    Pulls all product and store data from Salla API
    and creates KB documents automatically.
    """

    def __init__(self, salla_api_url: str, access_token: str):
        self.api_url = salla_api_url
        self.token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

    async def fetch_all_products(self) -> list[SallaProduct]:
        """Fetch all products from Salla store."""
        import httpx

        products = []
        page = 1

        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                resp = await client.get(
                    f"{self.api_url}/products",
                    headers=self.headers,
                    params={"page": page, "per_page": 50},
                )

                if resp.status_code != 200:
                    logger.error(f"Salla products API error: {resp.status_code}")
                    break

                data = resp.json()
                items = data.get("data", [])

                if not items:
                    break

                for item in items:
                    products.append(SallaProduct(
                        id=str(item.get("id", "")),
                        name=item.get("name", ""),
                        price=float(item.get("price", {}).get("amount", 0)),
                        description=item.get("description", "") or "",
                        currency=item.get("price", {}).get("currency", "SAR"),
                        sku=item.get("sku"),
                        in_stock=item.get("status") == "sale",
                        quantity=item.get("quantity"),
                        images=[img.get("url", "") for img in item.get("images", [])[:3]],
                        categories=[cat.get("name", "") for cat in item.get("categories", [])],
                        sizes=_extract_options(item, "size"),
                        colors=_extract_options(item, "color"),
                        url=item.get("url"),
                    ))

                pagination = data.get("pagination", {})
                if page >= pagination.get("totalPages", 1):
                    break
                page += 1

        logger.info(f"Fetched {len(products)} products from Salla")
        return products

    async def fetch_store_info(self) -> SallaStoreInfo:
        """Fetch store settings and policies."""
        import httpx

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.api_url}/store/info",
                headers=self.headers,
            )

            if resp.status_code != 200:
                logger.error(f"Salla store info API error: {resp.status_code}")
                return SallaStoreInfo(name="المتجر", description="")

            data = resp.json().get("data", {})

            return SallaStoreInfo(
                name=data.get("name", "المتجر"),
                description=data.get("description", ""),
                return_policy=data.get("return_policy"),
                shipping_policy=data.get("shipping_policy"),
                exchange_policy=data.get("exchange_policy"),
                working_hours=data.get("working_hours"),
                payment_methods=[m.get("name", "") for m in data.get("payment_methods", [])],
                shipping_companies=[s.get("name", "") for s in data.get("shipping_companies", [])],
            )


# ──────────────────────────────────────────────
# KB Document Generator — تحويل بيانات سلة لـ KB
# ──────────────────────────────────────────────

def product_to_kb_content(product: SallaProduct) -> str:
    """Convert a Salla product to Arabic KB document content."""
    lines = [
        f"## المنتج: {product.name}",
        f"السعر: {product.price} {product.currency}",
    ]

    if product.description:
        # نظّف HTML tags من الوصف
        import re
        clean_desc = re.sub(r'<[^>]+>', '', product.description).strip()
        if clean_desc:
            lines.append(f"الوصف: {clean_desc[:500]}")

    if product.sizes:
        lines.append(f"المقاسات المتوفرة: {', '.join(product.sizes)}")

    if product.colors:
        lines.append(f"الألوان المتوفرة: {', '.join(product.colors)}")

    if product.categories:
        lines.append(f"التصنيف: {', '.join(product.categories)}")

    if product.brand:
        lines.append(f"العلامة التجارية: {product.brand}")

    lines.append(f"حالة التوفر: {'متوفر ✅' if product.in_stock else 'نفد المخزون ❌'}")

    if product.quantity is not None and product.quantity < 10 and product.in_stock:
        lines.append(f"⚠️ الكمية المتبقية: {product.quantity} فقط")

    if product.url:
        lines.append(f"رابط المنتج: {product.url}")

    return "\n".join(lines)


def store_policies_to_kb_content(store: SallaStoreInfo) -> list[dict]:
    """Convert store policies to multiple KB documents."""
    docs = []

    if store.return_policy:
        docs.append({
            "title": "سياسة الإرجاع والاسترداد",
            "content": store.return_policy,
            "content_type": "policy",
        })

    if store.shipping_policy:
        docs.append({
            "title": "سياسة الشحن والتوصيل",
            "content": store.shipping_policy,
            "content_type": "policy",
        })

    if store.exchange_policy:
        docs.append({
            "title": "سياسة التبديل والاستبدال",
            "content": store.exchange_policy,
            "content_type": "policy",
        })

    if store.working_hours:
        docs.append({
            "title": "مواعيد العمل",
            "content": store.working_hours,
            "content_type": "general",
        })

    if store.payment_methods:
        docs.append({
            "title": "طرق الدفع المتاحة",
            "content": f"طرق الدفع المتاحة في المتجر: {', '.join(store.payment_methods)}",
            "content_type": "general",
        })

    if store.shipping_companies:
        docs.append({
            "title": "شركات الشحن",
            "content": f"شركات الشحن المعتمدة: {', '.join(store.shipping_companies)}",
            "content_type": "general",
        })

    return docs


# ──────────────────────────────────────────────
# Full Sync Pipeline
# ──────────────────────────────────────────────

async def run_full_sync(
    workspace_id: str,
    salla_api_url: str,
    salla_token: str,
    db_session,
    kb_service,  # KB document creation service
) -> SyncResult:
    """
    Full sync pipeline:
    1. Fetch products from Salla
    2. Fetch store info/policies
    3. Create/update KB documents
    4. Trigger re-embedding for updated docs
    """
    import time
    start = time.time()

    result = SyncResult(
        products_synced=0,
        policies_synced=0,
        kb_documents_created=0,
        kb_documents_updated=0,
    )

    syncer = SallaAutoSync(salla_api_url, salla_token)

    # 1. Sync Products
    try:
        products = await syncer.fetch_all_products()
        for product in products:
            content = product_to_kb_content(product)

            # Check if KB doc already exists for this product
            existing = await kb_service.find_by_salla_id(
                workspace_id, f"product_{product.id}"
            )

            if existing:
                await kb_service.update_document(
                    existing.id,
                    content=content,
                    metadata={"salla_product_id": product.id, "synced_at": datetime.utcnow().isoformat()},
                )
                result.kb_documents_updated += 1
            else:
                await kb_service.create_document(
                    workspace_id=workspace_id,
                    title=f"منتج: {product.name}",
                    content=content,
                    content_type="product_catalog",
                    status="approved",  # Auto-approve synced products
                    metadata={"salla_product_id": product.id, "synced_at": datetime.utcnow().isoformat()},
                )
                result.kb_documents_created += 1

            result.products_synced += 1

    except Exception as e:
        logger.error(f"Product sync error: {e}")
        result.errors.append(f"Product sync: {str(e)}")

    # 2. Sync Store Policies
    try:
        store_info = await syncer.fetch_store_info()
        policy_docs = store_policies_to_kb_content(store_info)

        for doc in policy_docs:
            existing = await kb_service.find_by_title(workspace_id, doc["title"])

            if existing:
                await kb_service.update_document(
                    existing.id,
                    content=doc["content"],
                    metadata={"synced_at": datetime.utcnow().isoformat()},
                )
                result.kb_documents_updated += 1
            else:
                await kb_service.create_document(
                    workspace_id=workspace_id,
                    title=doc["title"],
                    content=doc["content"],
                    content_type=doc["content_type"],
                    status="approved",
                    metadata={"synced_at": datetime.utcnow().isoformat()},
                )
                result.kb_documents_created += 1

            result.policies_synced += 1

    except Exception as e:
        logger.error(f"Policy sync error: {e}")
        result.errors.append(f"Policy sync: {str(e)}")

    result.sync_time = round(time.time() - start, 2)

    logger.info(
        f"Salla sync complete: {result.products_synced} products, "
        f"{result.policies_synced} policies, "
        f"{result.kb_documents_created} created, "
        f"{result.kb_documents_updated} updated, "
        f"{result.sync_time}s"
    )

    return result


# ──────────────────────────────────────────────
# Webhook Handler — لتحديث المنتجات تلقائياً
# ──────────────────────────────────────────────

async def handle_salla_product_webhook(
    workspace_id: str,
    event: str,
    product_data: dict,
    kb_service,
) -> None:
    """
    Handle Salla product webhooks for real-time sync.
    Events: product.created, product.updated, product.deleted
    """
    product_id = str(product_data.get("id", ""))

    if event == "product.deleted":
        existing = await kb_service.find_by_salla_id(workspace_id, f"product_{product_id}")
        if existing:
            await kb_service.archive_document(existing.id)
            logger.info(f"Archived KB doc for deleted product {product_id}")
        return

    # product.created or product.updated
    product = SallaProduct(
        id=product_id,
        name=product_data.get("name", ""),
        price=float(product_data.get("price", {}).get("amount", 0)),
        description=product_data.get("description", ""),
        in_stock=product_data.get("status") == "sale",
        quantity=product_data.get("quantity"),
        sizes=_extract_options(product_data, "size"),
        colors=_extract_options(product_data, "color"),
        url=product_data.get("url"),
    )

    content = product_to_kb_content(product)
    existing = await kb_service.find_by_salla_id(workspace_id, f"product_{product_id}")

    if existing:
        await kb_service.update_document(existing.id, content=content)
        logger.info(f"Updated KB doc for product {product_id}")
    else:
        await kb_service.create_document(
            workspace_id=workspace_id,
            title=f"منتج: {product.name}",
            content=content,
            content_type="product_catalog",
            status="approved",
            metadata={"salla_product_id": product_id},
        )
        logger.info(f"Created KB doc for new product {product_id}")


# ──────────────────────────────────────────────
# Order Webhook — لتتبع الطلبات وربط Revenue
# ──────────────────────────────────────────────

async def handle_salla_order_webhook(
    workspace_id: str,
    event: str,
    order_data: dict,
    db_session,
) -> None:
    """
    Handle Salla order webhooks for revenue attribution.
    Events: order.created, order.updated, order.completed
    """
    from sqlalchemy import text

    if event == "order.created":
        customer_phone = order_data.get("customer", {}).get("mobile")
        order_amount = float(order_data.get("amounts", {}).get("total", {}).get("amount", 0))
        order_id = str(order_data.get("id", ""))

        if not customer_phone:
            return

        # Match with customer who had a conversation in last 24 hours
        import hashlib
        import uuid as uuid_mod

        phone_hash = hashlib.sha256(customer_phone.encode()).hexdigest()

        result = await db_session.execute(
            text("""
                SELECT c.id as customer_id, conv.id as conversation_id
                FROM customers c
                JOIN conversations conv ON conv.customer_id = c.id
                WHERE c.workspace_id = :wid
                AND c.channel_identifier_hash = :phone_hash
                AND conv.created_at > NOW() - INTERVAL '24 hours'
                ORDER BY conv.created_at DESC
                LIMIT 1
            """),
            {"wid": workspace_id, "phone_hash": phone_hash},
        )

        match = result.fetchone()
        if match:
            try:
                # Insert into revenue_events (Revenue Attribution)
                from radd.db.models import RevenueEvent

                rev_event = RevenueEvent(
                    workspace_id=uuid_mod.UUID(workspace_id),
                    customer_id=uuid_mod.UUID(str(match.customer_id)),
                    conversation_id=uuid_mod.UUID(str(match.conversation_id)) if match.conversation_id else None,
                    event_type="assisted_sale",
                    amount_sar=order_amount,
                    order_id=order_id,
                    metadata_={"platform": "salla", "event": event},
                )
                db_session.add(rev_event)

                # Update customers table
                await db_session.execute(
                    text("""
                        UPDATE customers
                        SET total_attributed_revenue = COALESCE(total_attributed_revenue, 0) + :amount,
                            salla_total_orders = COALESCE(salla_total_orders, 0) + 1,
                            salla_total_revenue = COALESCE(salla_total_revenue, 0) + :amount
                        WHERE id = :cid
                    """),
                    {"amount": order_amount, "cid": str(match.customer_id)},
                )
                await db_session.commit()

                logger.info(
                    f"Revenue attributed: {order_amount} SAR to customer {match.customer_id} "
                    f"(order {order_id}, workspace {workspace_id})"
                )
            except Exception as e:
                logger.warning(f"Revenue attribution failed for order {order_id}: {e}")
                await db_session.rollback()
                # Never block order processing because of attribution failure


def _extract_options(product_data: dict, option_name: str) -> list[str]:
    """Extract product options (sizes, colors) from Salla product data."""
    options = product_data.get("options", [])
    for opt in options:
        if option_name.lower() in (opt.get("name", "")).lower():
            return [v.get("name", "") for v in opt.get("values", [])]
    return []
