"""Pure scoring rules: accuracy matching and reflex score (OQ-48, OQ-51, Addendum 2).

Rounding rule (pinned): round half up to an integer, ``floor(x + 0.5)``.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Sequence
from difflib import SequenceMatcher

LEVEL_LIMITS_MS: dict[int, int] = {1: 6000, 2: 5000, 3: 3000, 4: 8000}
FUZZY_CAP = 60
SPEED_BONUS_MIN_ACCURACY = 70
SPEED_FLOOR_MS = 1000
TIMEOUT_GRACE_MS = 2000

_WORD = re.compile(r"\w+")


def round_half_up(x: float) -> int:
    return math.floor(x + 0.5)


def tokens(text: str | None) -> list[str]:
    """NFKC, lowercase, punctuation stripped, split into words."""
    if not text:
        return []
    return _WORD.findall(unicodedata.normalize("NFKC", text).lower())


def _contains_sequence(haystack: list[str], needle: list[str]) -> bool:
    n = len(needle)
    return n > 0 and any(haystack[i:i + n] == needle for i in range(len(haystack) - n + 1))


def label_accuracy(transcript: str | None, accepted: Sequence[str]) -> int:
    """100 if any accepted answer is a whole word(s) in the transcript, else fuzzy capped at 60."""
    said = tokens(transcript)
    if not said:
        return 0
    best = 0
    for answer in accepted:
        want = tokens(answer)
        if _contains_sequence(said, want):
            return 100
        if want:
            ratio = SequenceMatcher(None, " ".join(want), " ".join(said)).ratio()
            best = max(best, min(FUZZY_CAP, round_half_up(100 * ratio)))
    return best


def sentence_accuracy(transcript: str | None, sentence: str) -> int:
    """Word-level recall of the target sentence (extra spoken words are not penalised)."""
    target, said = tokens(sentence), tokens(transcript)
    if not target or not said:
        return 0
    matched = sum(b.size for b in SequenceMatcher(None, target, said).get_matching_blocks())
    return round_half_up(100 * matched / len(target))


def accuracy(item_type: str, transcript: str | None, accepted: Sequence[str]) -> int:
    if item_type == "label":
        return label_accuracy(transcript, accepted)
    return max((sentence_accuracy(transcript, s) for s in accepted), default=0)


def is_timeout(reflex_ms: float, limit_ms: float) -> bool:
    return reflex_ms > limit_ms


def reflex_ms_valid(reflex_ms: float, limit_ms: float) -> bool:
    return 0 <= reflex_ms <= limit_ms + TIMEOUT_GRACE_MS


def speed(reflex_ms: float, limit_ms: float) -> float:
    raw = (limit_ms - reflex_ms) / (limit_ms - SPEED_FLOOR_MS) * 100
    return min(100.0, max(0.0, raw))


def reflex_score(acc: float, reflex_ms: float, limit_ms: float) -> float:
    """0.6*acc + 0.4*speed*[acc>=70]; a timeout (ms > limit) scores 0."""
    if is_timeout(reflex_ms, limit_ms):
        return 0.0
    bonus = speed(reflex_ms, limit_ms) if acc >= SPEED_BONUS_MIN_ACCURACY else 0.0
    return 0.6 * acc + 0.4 * bonus
