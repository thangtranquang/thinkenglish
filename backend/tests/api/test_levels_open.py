"""Practice levels 2 and 3 are open from the start (no unlock gate)."""
from backend.tests.helpers.practice import DESCRIPTIONS, att


def test_description_level_is_open_without_any_prior_progress(guest):
    r = guest.post("/api/attempts", json=att(DESCRIPTIONS[0], item_type="sentence", transcript="hello"))
    assert r.status_code == 201
    assert r.json()["unlocked_levels"] == [1, 2, 3]
