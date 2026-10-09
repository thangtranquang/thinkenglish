"""TC-3.9, 3.19, 4.19 - idle rule, prior sessions, gate truth table (DT-10)."""
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.services import policy

T0 = datetime(2026, 3, 2, 10, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("delta,expected", [(1799, False), (1800, False), (1801, True)])
def test_idle_strictly_greater(delta, expected):  # TC-3.9
    assert policy.is_new_session(T0, T0 + timedelta(seconds=delta), 1800) is expected


@pytest.mark.parametrize("flags,expected", [
    ([True, True, False], 2), ([True, False, False], 1), ([True], 0), ([], 0),
])
def test_prior_write_sessions(flags, expected):  # TC-3.19
    assert policy.prior_write_sessions(flags) == expected


@pytest.mark.parametrize("prior,free,expected", [
    (0, 1, False), (1, 1, True), (2, 1, True), (0, 0, True), (2, 3, False), (3, 3, True),
])
def test_gate_required(prior, free, expected):  # TC-4.19
    assert policy.gate_required(prior, free) is expected


@pytest.mark.parametrize("kind,prior,free,new,flag,expected", [
    ("guest", 0, 1, True, False, False),
    ("guest", 1, 1, True, False, True),
    ("guest", 1, 1, False, False, False),
    ("guest", 1, 1, False, True, True),
    ("guest", 1, 3, True, True, False),
    ("registered", 5, 1, True, True, False),
    ("system", 5, 1, True, True, False),
])
def test_gate_state(kind, prior, free, new, flag, expected):  # TC-4.19
    assert policy.gate_state(kind, prior, free, new, flag) is expected
