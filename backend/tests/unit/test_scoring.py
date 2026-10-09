"""TC-28.2, 28.3, 29.2, 29.18 - accuracy and reflex score tables (DT-1, DT-4, DT-4b)."""
import pytest

from backend.app.services import scoring

SENT = "A red cup is on the table"


@pytest.mark.parametrize("transcript,expected", [
    ("cup", 100), ("a cup", 100), ("Cup!", 100), ("CUP", 100), ("ＣＵＰ", 100),
    ("a red cup", 100), ("cup.", 100), ("cupboard", 55), ("cups", 60), ("cap", 60),
    ("dog", 0), ("", 0), (None, 0),
])
def test_label_accuracy(transcript, expected):  # TC-28.2
    assert scoring.label_accuracy(transcript, ["cup"]) == expected


def test_label_any_accepted_answer():
    assert scoring.label_accuracy("my mug", ["mug", "cup"]) == 100


@pytest.mark.parametrize("transcript,expected", [
    (SENT, 100), ("a red cup on table", 71),
    ("um a red cup is on the table please", 100), ("the table", 29), ("", 0),
])
def test_sentence_accuracy(transcript, expected):  # TC-28.2
    assert scoring.sentence_accuracy(transcript, SENT) == expected


def test_accuracy_dispatch():
    assert scoring.accuracy("label", "cup", ["cup"]) == 100
    assert scoring.accuracy("sentence", "the table", [SENT]) == 29


def test_round_half_up():
    assert scoring.round_half_up(0.5) == 1
    assert scoring.round_half_up(2.5) == 3
    assert scoring.round_half_up(71.4) == 71


@pytest.mark.parametrize("level,ms,acc,expected", [
    (2, 3000, 100, 80), (2, 1000, 100, 100), (2, 500, 100, 100), (2, 5000, 100, 60),
    (2, 5400, 100, 0), (2, 7000, 100, 0), (3, 2000, 100, 80),
    (3, 2000, 69, 41.4), (2, 3000, 70, 62), (1, 500, 0, 0), (1, 500, 60, 36), (4, 4500, 100, 80),
])
def test_reflex_score(level, ms, acc, expected):  # TC-28.3
    got = scoring.reflex_score(acc, ms, scoring.LEVEL_LIMITS_MS[level])
    assert got == pytest.approx(expected, abs=1e-9)


def test_level_limits():  # TC-29.2
    assert scoring.LEVEL_LIMITS_MS == {1: 6000, 2: 5000, 3: 3000, 4: 8000}


def test_speed_boundaries():  # TC-29.18
    assert scoring.speed(1000, 5000) == 100
    assert scoring.speed(500, 5000) == 100
    assert scoring.speed(5000, 5000) == 0
    assert scoring.speed(5001, 5000) == 0


def test_timeout_only_above_limit_and_range():
    assert not scoring.is_timeout(5000, 5000)
    assert scoring.is_timeout(5001, 5000)
    assert scoring.reflex_ms_valid(7000, 5000)
    assert not scoring.reflex_ms_valid(7001, 5000)
    assert not scoring.reflex_ms_valid(-1, 5000)
