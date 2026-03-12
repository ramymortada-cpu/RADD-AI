"""RADD AI — Entity Extractor: orders, shipping, products, amounts"""
import re
from dataclasses import dataclass, field

@dataclass
class ExtractedEntities:
    order_numbers: list[str] = field(default_factory=list)
    shipping_companies: list[str] = field(default_factory=list)
    product_mentions: list[str] = field(default_factory=list)
    monetary_amounts: list[str] = field(default_factory=list)

ORDER_PATTERNS = [re.compile(r"(?:طلب|رقم|order|#)\s*#?\s*(\d{4,10})",re.I), re.compile(r"#(\d{4,10})"), re.compile(r"(?:طلبي|طلبيتي)\s+(\d{4,10})")]
SHIPPING = {"ارامكس":"Aramex","aramex":"Aramex","سمسا":"SMSA","smsa":"SMSA","dhl":"DHL","فيدكس":"FedEx","fedex":"FedEx","ناقل":"Naqel","naqel":"Naqel","زاجل":"Zajil","البريد السعودي":"Saudi Post","سبل":"SPL","imile":"iMile","ايمايل":"iMile"}
MONEY = [re.compile(r"(\d+(?:\.\d{1,2})?)\s*(?:ريال|ر\.س|sar|رس)",re.I)]
PRODUCT_TRIGGERS = ["عن","سعر","منتج","عندكم","متوفر","موجود","ابغى","ابي","بكم","كم سعر"]

def extract_entities(text: str) -> ExtractedEntities:
    if not text: return ExtractedEntities()
    tl = text.lower(); e = ExtractedEntities()
    for p in ORDER_PATTERNS:
        for m in p.finditer(text):
            n = m.group(1)
            if n not in e.order_numbers: e.order_numbers.append(n)
    for kw, norm in SHIPPING.items():
        if kw in tl and norm not in e.shipping_companies: e.shipping_companies.append(norm)
    for t in PRODUCT_TRIGGERS:
        for m in re.finditer(rf"{t}\s+([\u0600-\u06FF\s]{{2,30}}?)(?:\?|؟|\.|$|،)", text, re.U):
            mention = m.group(1).strip()
            if len(mention) > 2 and mention not in e.product_mentions: e.product_mentions.append(mention)
    for p in MONEY:
        for m in p.finditer(text):
            if m.group(1) not in e.monetary_amounts: e.monetary_amounts.append(m.group(1))
    return e

def entities_to_dict(e: ExtractedEntities) -> dict:
    return {"order_numbers":e.order_numbers,"shipping_companies":e.shipping_companies,"product_mentions":e.product_mentions,"monetary_amounts":e.monetary_amounts}
