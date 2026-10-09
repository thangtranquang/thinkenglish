"""TC-16.14, 32.10 - XP, level, streak, mastery (DT-5, DT-7)."""
from datetime import datetime, timezone

import pytest

from backend.app.services import stats

UTC = timezone.utc
TODAY = datetime(2026, 3, 2, 5, 0, tzinfo=UTC)


@pytest.mark.parametrize("score,xp", [(100, 10), (70, 10), (69, 2), (0, 2), (None, 2)])
def test_xp_per_attempt(score, xp):
    assert stats.xp_for_score(score) == xp


def test_xp_sum():
    assert sum(stats.xp_for_score(s) for s in (80, 50)) == 12


@pytest.mark.parametrize("xp,level,progress", [
    (0, 1, 0.0), (499, 1, 0.998), (500, 2, 0.0), (999, 2, 0.998), (1000, 3, 0.0), (1200, 3, 0.4),
])
def test_level(xp, level, progress):  # TC-16.14
    lv, pr = stats.level_from_xp(xp)
    assert lv == level and pr == pytest.approx(progress, abs=1e-9)


def _d(day: str) -> datetime:
    return datetime.fromisoformat(f"2026-{day}T05:00:00+00:00")


@pytest.mark.parametrize("days,expected", [
    (["03-01", "03-02"], 2), (["03-01"], 1), (["03-02"], 1), (["02-28"], 0),
    (["03-02", "02-28"], 1), (["03-01", "02-28", "02-27"], 3), ([], 0),
])
def test_streak(days, expected):  # TC-16.14
    assert stats.streak_days([_d(d) for d in days], TODAY) == expected


def test_ict_midnight():  # TC-16.14
    a = datetime(2026, 3, 1, 16, 59, 59, tzinfo=UTC)
    b = datetime(2026, 3, 1, 17, 0, 1, tzinfo=UTC)
    assert stats.ict_date(a).isoformat() == "2026-03-01"
    assert stats.ict_date(b).isoformat() == "2026-03-02"
    assert stats.streak_days([a, b], b) == 2


@pytest.mark.parametrize("scores,mean,label", [
    ([], None, "Chưa học"), ([59.99], 59.99, "Cần ôn"), ([60], 60, "Đang học"),
    ([84.99], 84.99, "Đang học"), ([85], 85, "Đã thuộc"), ([80, 90], 85, "Đã thuộc"),
    ([50, 60, 70], 60, "Đang học"), ([0, 100, 100, 100, 100, 100], 100, "Đã thuộc"),
])
def test_mastery(scores, mean, label):  # TC-32.10
    got = stats.mastery_mean(scores)
    assert got == (pytest.approx(mean) if mean is not None else None)
    assert stats.mastery_label(scores) == label
