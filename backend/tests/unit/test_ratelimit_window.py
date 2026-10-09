"""TC-13.17 - sliding window (DT-11): 5 per 900 s, failures at t=0,100,200,300,400."""
import pytest

from backend.app.services import policy

EVENTS = [0, 100, 200, 300, 400]


@pytest.mark.parametrize("now,exceeded,retry", [
    (500, True, 400), (899, True, 1), (900, False, None), (1000, False, None),
])
def test_window(now, exceeded, retry):  # TC-13.17
    assert policy.window_exceeded(EVENTS, now, 5, 900) is exceeded
    if exceeded:
        assert policy.retry_after(EVENTS, now, 5, 900) == retry


def test_count_in_window_boundary():  # TC-13.17
    assert policy.count_in_window(EVENTS, 900, 900) == 4
    assert policy.count_in_window(EVENTS, 1000, 900) == 3
