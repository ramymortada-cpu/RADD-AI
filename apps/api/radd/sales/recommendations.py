"""
Product Recommendations Engine v1 — Rule-based.

Strategies:
1. Cross-sell: "العملاء الذين اشتروا X اشتروا أيضاً Y"
2. Upsell: "فيه مقاس أكبر / نسخة أفضل بسعر أوفر"
3. Price alternative: "عندنا بديل بسعر أقل"

v1 uses simple rules and product metadata.
v2 (post-pilot) will use order history analysis.
"""

from __future__ import annotations

import logging
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger("radd.sales.recommendations")


# ─── Models ───


class Product(BaseModel):
    id: str = ""
    name: str
    price: float
    category: str = ""
    tags: list[str] = []
    size: str = ""  # e.g., "50ml", "100ml"
    in_stock: bool = True


class Recommendation(BaseModel):
    product: Product
    strategy: str  # "cross_sell" | "upsell" | "price_alternative"
    reason_ar: str  # Arabic explanation for the customer
    confidence: float = 0.7


# ─── Engine ───


class RecommendationEngine:
    """
    Rule-based recommendation engine.

    Uses product catalog (loaded from workspace KB or Salla API)
    to suggest relevant products during sales conversations.
    """

    def __init__(self, catalog: list[Product] | None = None):
        self._catalog = catalog or []

    def load_catalog(self, products: list[dict]) -> None:
        """Load product catalog from dicts (e.g., from Salla API or DB)."""
        self._catalog = [
            Product(**p) if isinstance(p, dict) else p for p in products
        ]
        logger.info("Catalog loaded: %d products", len(self._catalog))

    def get_cross_sell(
        self,
        current_product: Product,
        dialect: str = "gulf",
        max_results: int = 2,
    ) -> list[Recommendation]:
        """
        Find complementary products in the same or related category.

        Logic: Same category, different product, similar price range (±50%).
        """
        if not self._catalog:
            return []

        recommendations = []
        price_min = current_product.price * 0.3
        price_max = current_product.price * 1.5

        for product in self._catalog:
            if product.id == current_product.id:
                continue
            if not product.in_stock:
                continue

            score = 0.0

            # Same category boost
            if product.category and product.category == current_product.category:
                score += 0.3

            # Shared tags boost
            shared_tags = set(product.tags) & set(current_product.tags)
            score += len(shared_tags) * 0.15

            # Price range compatibility
            if price_min <= product.price <= price_max:
                score += 0.2

            if score >= 0.3:
                reason = self._format_cross_sell_reason(
                    current_product.name, product.name, dialect
                )
                recommendations.append(
                    Recommendation(
                        product=product,
                        strategy="cross_sell",
                        reason_ar=reason,
                        confidence=min(score, 0.95),
                    )
                )

        # Sort by confidence, take top N
        recommendations.sort(key=lambda r: r.confidence, reverse=True)
        return recommendations[:max_results]

    def get_upsell(
        self,
        current_product: Product,
        dialect: str = "gulf",
    ) -> Optional[Recommendation]:
        """
        Find a better/larger version of the same product.

        Logic: Same category, higher price, similar name/tags.
        """
        if not self._catalog:
            return None

        best = None
        best_score = 0.0

        for product in self._catalog:
            if product.id == current_product.id:
                continue
            if not product.in_stock:
                continue
            if product.price <= current_product.price:
                continue  # Must be more expensive for upsell

            score = 0.0

            # Same category
            if product.category == current_product.category:
                score += 0.4

            # Shared tags (indicates same product line)
            shared_tags = set(product.tags) & set(current_product.tags)
            score += len(shared_tags) * 0.2

            # Price not too much higher (max 2x)
            if product.price <= current_product.price * 2:
                score += 0.2

            if score > best_score:
                best_score = score
                best = product

        if best and best_score >= 0.4:
            reason = self._format_upsell_reason(
                current_product, best, dialect
            )
            return Recommendation(
                product=best,
                strategy="upsell",
                reason_ar=reason,
                confidence=min(best_score, 0.95),
            )

        return None

    def get_price_alternative(
        self,
        current_product: Product,
        dialect: str = "gulf",
    ) -> Optional[Recommendation]:
        """
        Find a cheaper alternative (for price objections).

        Logic: Same category, lower price, in stock.
        """
        if not self._catalog:
            return None

        best = None
        best_score = 0.0

        for product in self._catalog:
            if product.id == current_product.id:
                continue
            if not product.in_stock:
                continue
            if product.price >= current_product.price:
                continue  # Must be cheaper

            score = 0.0

            # Same category
            if product.category == current_product.category:
                score += 0.5

            # Not too cheap (at least 40% of original — quality signal)
            if product.price >= current_product.price * 0.4:
                score += 0.3

            # Shared tags
            shared_tags = set(product.tags) & set(current_product.tags)
            score += len(shared_tags) * 0.1

            if score > best_score:
                best_score = score
                best = product

        if best and best_score >= 0.4:
            savings = current_product.price - best.price
            reason = self._format_alternative_reason(
                best, savings, dialect
            )
            return Recommendation(
                product=best,
                strategy="price_alternative",
                reason_ar=reason,
                confidence=min(best_score, 0.95),
            )

        return None

    def get_recommendations(
        self,
        current_product: Product,
        context: str = "inquiry",  # "inquiry" | "objection_price" | "browsing"
        dialect: str = "gulf",
    ) -> list[Recommendation]:
        """
        Get all relevant recommendations based on context.

        - inquiry → cross-sell + upsell
        - objection_price → price alternative + cross-sell cheaper
        - browsing → cross-sell
        """
        results = []

        if context == "objection_price":
            alt = self.get_price_alternative(current_product, dialect)
            if alt:
                results.append(alt)
            cheaper_cross = [
                r
                for r in self.get_cross_sell(current_product, dialect)
                if r.product.price < current_product.price
            ]
            results.extend(cheaper_cross[:1])

        elif context == "inquiry":
            upsell = self.get_upsell(current_product, dialect)
            if upsell:
                results.append(upsell)
            results.extend(
                self.get_cross_sell(current_product, dialect, max_results=2)
            )

        else:  # browsing
            results.extend(
                self.get_cross_sell(current_product, dialect, max_results=3)
            )

        return results

    # ─── Message Formatters ───

    def _format_cross_sell_reason(
        self, current_name: str, rec_name: str, dialect: str
    ) -> str:
        if dialect == "gulf":
            return f"كثير من عملائنا اللي أخذوا {current_name} أخذوا معاه {rec_name} 👌"
        elif dialect == "egyptian":
            return f"كتير من عملائنا اللي اشتروا {current_name} اشتروا كمان {rec_name} 👌"
        return f"كثير من العملاء الذين اشتروا {current_name} اشتروا أيضاً {rec_name} 👌"

    def _format_upsell_reason(
        self, current: Product, upsell: Product, dialect: str
    ) -> str:
        if dialect == "gulf":
            return f"لو تبي أوفر — {upsell.name} بـ {upsell.price} ريال يعطيك قيمة أكبر! 🔥"
        elif dialect == "egyptian":
            return f"لو عايز أوفر — {upsell.name} بـ {upsell.price} جنيه هيديك قيمة أكبر! 🔥"
        return f"للحصول على قيمة أفضل — {upsell.name} بسعر {upsell.price} يوفر لك أكثر! 🔥"

    def _format_alternative_reason(
        self, alt: Product, savings: float, dialect: str
    ) -> str:
        if dialect == "gulf":
            return f"عندنا {alt.name} بـ {alt.price} ريال — توفر {savings:.0f} ريال وجودته ممتازة! 💰"
        elif dialect == "egyptian":
            return f"عندنا {alt.name} بـ {alt.price} جنيه — هتوفر {savings:.0f} جنيه وجودته ممتازة! 💰"
        return f"لدينا {alt.name} بسعر {alt.price} — توفير {savings:.0f} بجودة ممتازة! 💰"
