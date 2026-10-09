"""TC-28.4, 28.5, 28.21 - quality map and SM-2 (DT-2, DT-3)."""
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.services.srs import SrsState, due_at, next_state, quality_from_score


@pytest.mark.parametrize("score,q", [
    (100, 5), (95, 5), (90, 5), (89, 4), (85, 4), (80, 4), (79, 3), (75, 3), (70, 3),
    (69, 2), (55, 2), (50, 2), (49, 1), (25, 1), (20, 1), (19, 0), (10, 0), (0, 0),
])
def test_quality_map(score, q):  # TC-28.4
    assert quality_from_score(score) == q


@pytest.mark.parametrize("before,q,ease,reps,interval,lapses_added", [
    ((2.5, 0, 0, 0), 5, 2.6, 1, 1, 0),
    ((2.6, 1, 1, 0), 5, 2.7, 2, 6, 0),
    ((2.5, 2, 6, 0), 4, 2.5, 3, 15, 0),
    ((2.5, 2, 6, 0), 3, 2.36, 3, 14, 0),
    ((2.5, 3, 15, 0), 2, 2.18, 0, 1, 1),
    ((2.5, 3, 15, 0), 0, 1.7, 0, 1, 1),
    ((2.5, 0, 0, 0), 1, 1.96, 0, 1, 1),
    ((1.35, 3, 10, 0), 0, 1.3, 0, 1, 1),
    ((1.3, 2, 6, 0), 3, 1.3, 3, 8, 0),
])
def test_sm2_transitions(before, q, ease, reps, interval, lapses_added):  # TC-28.5
    s = next_state(SrsState(*before), q)
    assert s.ease == pytest.approx(ease, abs=1e-9)
    assert (s.reps, s.interval, s.lapses) == (reps, interval, lapses_added)


def test_worked_examples_and_floor():  # TC-28.21
    s = next_state(SrsState(2.5, 2, 6, 0), 4)
    assert (s.interval, s.ease) == (15, 2.5)
    s = SrsState(2.5, 2, 6, 0)
    eases = []
    for _ in range(20):
        s = next_state(s, 3)
        eases.append(s.ease)
    expected = [2.36, 2.22, 2.08, 1.94, 1.80, 1.66, 1.52, 1.38] + [1.3] * 12
    for got, want in zip(eases, expected):
        assert got == pytest.approx(want, abs=1e-9)
    assert min(eases) >= 1.3


def test_due_at():
    now = datetime(2026, 3, 2, tzinfo=timezone.utc)
    assert due_at(now, 6) == now + timedelta(days=6)
