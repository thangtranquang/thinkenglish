"""TC-8.3, 8.4 - birth year and guardian rules (DT-9)."""
from datetime import datetime, timezone

import pytest

from backend.app.services import validators as v


def test_current_year_ict():
    assert v.current_year_ict(datetime(2026, 6, 1, tzinfo=timezone.utc)) == 2026
    assert v.current_year_ict(datetime(2026, 12, 31, 18, 0, tzinfo=timezone.utc)) == 2027


@pytest.mark.parametrize("year,age,guardian", [
    (2016, 10, True), (2011, 15, True), (2010, 16, False), (1926, 100, False),
])
def test_birth_year_ok(year, age, guardian):  # TC-8.3
    assert v.validate_birth_year(year, 2026) == age
    assert v.guardian_required(age) is guardian


def test_too_young_message():  # TC-8.3
    with pytest.raises(v.ValidationFailure) as e:
        v.validate_birth_year(2017, 2026)
    assert "ReflexEnglish dành cho học sinh từ 10 tuổi" in str(e.value)


@pytest.mark.parametrize("year", [1925, 2027, "abc", 2000.5, True, None])
def test_birth_year_reject(year):  # TC-8.3
    with pytest.raises(v.ValidationFailure):
        v.validate_birth_year(year, 2026)


def test_new_year_ict_boundary():  # TC-8.3
    assert v.validate_birth_year(2017, 2027) == 10
    with pytest.raises(v.ValidationFailure):
        v.validate_birth_year(2018, 2027)


def _email(n: int) -> str:
    return "a" * (n - len("@b.vn")) + "@b.vn"


def test_guardian_under_16():  # TC-8.4
    v.validate_guardian(12, "mom@example.com", True)
    v.validate_guardian(12, _email(254), True)
    for email, consent in [(None, True), ("mom@example.com", None), ("mom@example.com", False),
                           ("nomail", True), ("a@b", True), (_email(255), True)]:
        with pytest.raises(v.ValidationFailure):
            v.validate_guardian(12, email, consent)


def test_guardian_forbidden_at_16():  # TC-8.4
    v.validate_guardian(16, None, None)
    v.validate_guardian(16, None, False)
    for email, consent in [("mom@example.com", None), (None, True)]:
        with pytest.raises(v.ValidationFailure):
            v.validate_guardian(16, email, consent)
