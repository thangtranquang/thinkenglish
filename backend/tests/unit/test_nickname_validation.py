"""TC-8.1, 8.2 - nickname/password rules (DT-8); plus review-override rules (DT-15)."""
import pytest

from backend.app.services import validators as v


@pytest.mark.parametrize("raw,out", [
    ("abc", "abc"), ("a" * 20, "a" * 20), ("Ｍinh", "Minh"), ("a.b-c_d", "a.b-c_d"), (" abc ", "abc"),
])
def test_nickname_accept(raw, out):  # TC-8.1
    assert v.validate_nickname(raw) == out


@pytest.mark.parametrize("raw", [
    "ab", "a" * 21, "a b", "a@b", "a/b", "\U0001F600ab", "Nguyễn", "аbc",
    "a@b.vn", "0912345678", "admin", "Admin", "system", "",
])
def test_nickname_reject(raw):  # TC-8.1
    with pytest.raises(v.ValidationFailure):
        v.validate_nickname(raw)


@pytest.mark.parametrize("pw", ["x" * 8, "x" * 128, "Tr0ub4dor&3"])
def test_password_accept(pw):  # TC-8.2
    assert v.validate_password(pw, "bob") == pw


@pytest.mark.parametrize("pw", ["x" * 7, "x" * 129, "bobbobbob", "password", "12345678"])
def test_password_reject(pw):  # TC-8.2
    with pytest.raises(v.ValidationFailure):
        v.validate_password(pw, "bobbobbob")


LABELS = {"l1", "l2", "l3"}


def _ov(**kw):
    base = dict(title="t", labels=[{"id": "l1", "word": "cup", "x": 0.5, "y": 0.5}])
    base.update(kw)
    return base


def test_overrides_ok():
    v.validate_review_overrides(LABELS, **_ov())
    v.validate_review_overrides(LABELS, **_ov(title="x" * 60))
    v.validate_review_overrides(LABELS, **_ov(labels=[{"id": "l1", "word": "c", "x": 0, "y": 1}]))


@pytest.mark.parametrize("kw", [
    dict(title="x" * 61),
    dict(labels=[{"id": "l1", "word": "", "x": 0.5, "y": 0.5}]),
    dict(labels=[{"id": "l1", "word": "x" * 41, "x": 0.5, "y": 0.5}]),
    dict(labels=[{"id": "l1", "word": "Cup", "x": 0.1, "y": 0.1},
                 {"id": "l2", "word": "cup", "x": 0.2, "y": 0.2}]),
    dict(labels=[]),
    dict(labels=[{"id": f"l{i}", "word": f"w{i}", "x": 0.1, "y": 0.1} for i in range(9)]),
    dict(labels=[{"id": "l1", "word": "a", "x": 1.01, "y": 0.5}]),
    dict(labels=[{"id": "l1", "word": "a", "x": 0.5, "y": -0.01}]),
    dict(labels=[{"id": "zzz", "word": "a", "x": 0.5, "y": 0.5}]),
    dict(labels=[{"word": "a", "x": 0.5, "y": 0.5}]),
])
def test_overrides_reject(kw):
    with pytest.raises(v.ValidationFailure):
        v.validate_review_overrides(LABELS, **_ov(**kw))
