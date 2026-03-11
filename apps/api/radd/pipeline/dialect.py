"""
Dialect detector v0 — rule-based keyword matching.
Detects: gulf, egyptian, msa (default).
v1 (Sprint 2): replace with ML-based classifier.
"""
from dataclasses import dataclass

# ─── Dialect marker vocabulary ────────────────────────────────────────────────
# Normalized forms (no tashkeel, Alef/Ya normalized)

GULF_MARKERS = {
    "وش",     # what (Gulf)
    "ليش",    # why (Gulf)
    "عشان",   # because/in order to
    "كذا",    # like this
    "ايش",    # what
    "يبيله",  # he wants it
    "حق",     # for / belongs to
    "شفيه",   # what's wrong with him
    "ابي",    # I want
    "ابغى",   # I want
    "بغيت",   # I wanted
    "شلون",   # how
    "وين",    # where
    "متى",    # when (also MSA but strong in Gulf context)
    "هلا",    # hi (Gulf greeting)
    "هالشي",  # this thing
    "ماقدرت", # couldn't
}

EGYPTIAN_MARKERS = {
    "ايه",    # what
    "ليه",    # why
    "عشان",   # because
    "كده",    # like this
    "بتاع",   # belonging to
    "يعني",   # meaning / i.e.
    "جاي",    # coming
    "مش",     # not
    "بقى",    # then / so
    "دلوقتي", # now
    "اوضة",   # room
    "فين",    # where (Egyptian)
    "عامل",   # doing/making
    "اللي",   # which/that (common but stronger in Egyptian)
    "انهارده", # today
}


@dataclass
class DialectResult:
    dialect: str   # gulf | egyptian | msa
    confidence: float
    markers_found: list[str]


def detect_dialect(text: str) -> DialectResult:
    """
    Rule-based dialect detection.
    Scores by counting dialect-specific markers in normalized text.
    """
    words = set(text.lower().split())

    gulf_matches = [w for w in words if w in GULF_MARKERS]
    egyptian_matches = [w for w in words if w in EGYPTIAN_MARKERS]

    gulf_score = len(gulf_matches)
    egyptian_score = len(egyptian_matches)

    if gulf_score == 0 and egyptian_score == 0:
        return DialectResult(dialect="msa", confidence=0.6, markers_found=[])

    if gulf_score > egyptian_score:
        confidence = min(0.95, 0.7 + gulf_score * 0.05)
        return DialectResult(dialect="gulf", confidence=confidence, markers_found=gulf_matches)

    if egyptian_score > gulf_score:
        confidence = min(0.95, 0.7 + egyptian_score * 0.05)
        return DialectResult(dialect="egyptian", confidence=confidence, markers_found=egyptian_matches)

    # Tie: default to Gulf (primary market)
    return DialectResult(dialect="gulf", confidence=0.65, markers_found=gulf_matches)
