"""Pure progress statistics: XP, level, streak, mastery, unlock rules (OQ-23, 45, 52, 54).

Days are calendar days in Asia/Ho_Chi_Minh, which is a fixed UTC+7 (no DST), so a fixed
offset is used and no tz database is required.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date, datetime, timedelta, timezone

ICT = timezone(timedelta(hours=7), "Asia/Ho_Chi_Minh")
XP_PER_LEVEL = 500
XP_PASS = 10
XP_FAIL = 2
PASS_SCORE = 70
PRACTICE_LEVELS = 3
REFLEX_LEVELS = 4
REFLEX_MIN_ANSWERED = 5
REFLEX_UNLOCK_MEAN = 80
MASTERY_WINDOW = 5
MASTERY_LEARNING = 60
MASTERY_MASTERED = 85


def xp_for_score(score: float | None) -> int:
    return XP_PASS if score is not None and score >= PASS_SCORE else XP_FAIL


def level_from_xp(xp: int) -> tuple[int, float]:
    level, rest = divmod(max(0, xp), XP_PER_LEVEL)
    return level + 1, rest / XP_PER_LEVEL


def ict_date(moment: datetime) -> date:
    return moment.astimezone(ICT).date()


def streak_days(attempt_times: Iterable[datetime], now: datetime) -> int:
    """Consecutive ICT days with an attempt, ending today or yesterday."""
    days = {ict_date(t) for t in attempt_times}
    today = ict_date(now)
    day = today if today in days else today - timedelta(days=1)
    count = 0
    while day in days:
        count += 1
        day -= timedelta(days=1)
    return count


def mastery_mean(scores: Sequence[float]) -> float | None:
    """Mean of the last <= 5 scores (oldest first); None when there are none."""
    recent = list(scores)[-MASTERY_WINDOW:]
    return sum(recent) / len(recent) if recent else None


def mastery_label(scores: Sequence[float]) -> str:
    mean = mastery_mean(scores)
    if mean is None:
        return "Chưa học"
    if mean < MASTERY_LEARNING:
        return "Cần ôn"
    return "Đang học" if mean < MASTERY_MASTERED else "Đã thuộc"


def level_score(latest_scores: Sequence[float | None]) -> float:
    """Mean of the latest score per item; unattempted (None) counts as 0."""
    if not latest_scores:
        return 0.0
    return sum(s or 0 for s in latest_scores) / len(latest_scores)


def best_score(previous_best: float, current: float) -> float:
    return max(previous_best, current)


def meets_practice_unlock(score: float) -> bool:
    return score >= PASS_SCORE


def practice_unlocked_levels(best_scores: Sequence[float]) -> int:
    """Highest unlocked practice level given best scores of levels 1..n (level 1 always open)."""
    unlocked = 1
    for best in best_scores[:PRACTICE_LEVELS - 1]:
        if not meets_practice_unlock(best):
            break
        unlocked += 1
    return unlocked


def reflex_next_unlocked(unlocked: int, level_played: int, answered: int, mean_score: float) -> int:
    """Simplified reflex unlock: >=5 answered rounds and mean >= 80 at the frontier level."""
    if (level_played == unlocked and unlocked < REFLEX_LEVELS
            and answered >= REFLEX_MIN_ANSWERED and mean_score >= REFLEX_UNLOCK_MEAN):
        return unlocked + 1
    return unlocked
