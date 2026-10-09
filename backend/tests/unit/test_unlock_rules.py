"""TC-27.3, 29.19, 47.6 - practice and reflex unlock (DT-6, DT-6b)."""
import pytest

from backend.app.services import stats


def test_level_score_latest_unattempted_zero():  # TC-27.3
    assert stats.level_score([100, 80, 60, None]) == 60
    assert stats.level_score([100, 80, 80, 100]) == 90
    assert stats.level_score([]) == 0


def test_best_score_never_drops():  # TC-27.3
    best = stats.best_score(60, stats.level_score([100, 80, 80, 100]))
    assert best == 90
    best = stats.best_score(best, stats.level_score([50, 50, 50, 50]))
    assert best == 90
    assert stats.practice_unlocked_levels([best, 0, 0]) == 2


@pytest.mark.parametrize("mean,unlocked", [(69, False), (69.99, False), (70, True), (70.01, True)])
def test_unlock_threshold(mean, unlocked):  # TC-47.6
    assert stats.meets_practice_unlock(mean) is unlocked


def test_practice_chain():  # TC-27.3
    assert stats.practice_unlocked_levels([95, 60, 0]) == 2
    assert stats.practice_unlocked_levels([]) == 1
    assert stats.practice_unlocked_levels([95, 70, 0]) == 3


@pytest.mark.parametrize("score,answered,expected", [
    (80.0, 5, 2), (79.9, 5, 1), (100, 4, 1), (0, 5, 1),
])
def test_reflex_unlock(score, answered, expected):  # TC-29.19
    assert stats.reflex_next_unlocked(1, 1, answered, score) == expected


def test_reflex_unlock_only_at_frontier_and_cap():  # TC-29.19
    assert stats.reflex_next_unlocked(2, 1, 5, 95) == 2
    assert stats.reflex_next_unlocked(4, 4, 5, 95) == 4
    assert stats.reflex_next_unlocked(2, 2, 5, 90) == 3
