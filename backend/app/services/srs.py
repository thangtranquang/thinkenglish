"""Pure SM-2 spaced-repetition rules (OQ-47, Addendum 2 #1).

Ease is updated for the current quality first; the new interval uses the updated ease.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

EASE_DEFAULT = 2.5
EASE_FLOOR = 1.3


@dataclass(frozen=True)
class SrsState:
    ease: float = EASE_DEFAULT
    reps: int = 0
    interval: int = 0
    lapses: int = 0


def quality_from_score(score: float) -> int:
    for threshold, q in ((90, 5), (80, 4), (70, 3), (50, 2), (20, 1)):
        if score >= threshold:
            return q
    return 0


def ease_after(ease: float, q: int) -> float:
    delta = 0.1 - (5 - q) * (0.08 + 0.02 * (5 - q))
    return max(EASE_FLOOR, round(ease + delta, 4))


def next_state(state: SrsState, q: int) -> SrsState:
    ease = ease_after(state.ease, q)
    if q < 3:
        return SrsState(ease=ease, reps=0, interval=1, lapses=state.lapses + 1)
    if state.reps == 0:
        interval = 1
    elif state.reps == 1:
        interval = 6
    else:
        interval = math.floor(state.interval * ease + 0.5)
    return replace(state, ease=ease, reps=state.reps + 1, interval=interval)


def due_at(now: datetime, interval_days: int) -> datetime:
    return now + timedelta(days=interval_days)
