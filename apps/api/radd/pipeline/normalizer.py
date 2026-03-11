"""
Arabic text normalizer.
Removes/normalizes: tashkeel (diacritics), Alef variants, Ya, tatweel, whitespace.
No external dependencies — pure string operations.
"""
import re
import unicodedata

# ─── Arabic Unicode ranges ────────────────────────────────────────────────────
TASHKEEL = re.compile(r"[\u064B-\u065F\u0670]")  # fathah, dammah, kasrah, sukun, etc.
TATWEEL = re.compile(r"\u0640+")                  # kashida / tatweel
ALEF_VARIANTS = re.compile(r"[أإآٱ]")             # all Alef with hamza/madda → bare Alef
YA_VARIANTS = re.compile(r"ى")                    # Alef maqsura → ya
WAW_HAMZA = re.compile(r"ؤ")                      # waw hamza → waw
HAMZA_ON_YA = re.compile(r"ئ")                    # hamza on ya → ya
EXTRA_WHITESPACE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """
    Normalize Arabic text for consistent processing.
    Preserves meaning while removing orthographic variation.
    """
    if not text:
        return text

    # Remove tashkeel (diacritics)
    text = TASHKEEL.sub("", text)

    # Remove tatweel
    text = TATWEEL.sub("", text)

    # Normalize Alef variants to bare Alef (ا)
    text = ALEF_VARIANTS.sub("ا", text)

    # Normalize Ya variants (ى → ي)
    text = YA_VARIANTS.sub("ي", text)

    # Normalize Waw with Hamza (ؤ → و)
    text = WAW_HAMZA.sub("و", text)

    # Normalize Hamza on Ya (ئ → ي)
    text = HAMZA_ON_YA.sub("ي", text)

    # Normalize whitespace
    text = EXTRA_WHITESPACE.sub(" ", text).strip()

    return text


def is_arabic(text: str) -> bool:
    """Check if text contains Arabic characters (>30% Arabic chars)."""
    if not text:
        return False
    arabic_chars = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
    return arabic_chars / len(text) > 0.3
