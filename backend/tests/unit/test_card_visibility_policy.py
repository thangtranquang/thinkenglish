"""TC-25.13, 25.19 - image access matrix and share decision (DT-16, DT-16b)."""
import pytest

from backend.app.services import policy


@pytest.mark.parametrize("viewer,owner,system,vis,mod,ok", [
    ("u1", "u1", False, "private", "none", True),
    ("u2", "u1", True, "private", "none", True),
    (None, None, True, "private", "none", True),
    ("u2", "u1", False, "public", "approved", True),
    (None, "u1", False, "public", "approved", True),
    ("u2", "u1", False, "public", "pending", False),
    ("u2", "u1", False, "public", "rejected", False),
    ("u2", "u1", False, "private", "approved", False),
    (None, "u1", False, "private", "none", False),
])
def test_can_view(viewer, owner, system, vis, mod, ok):  # TC-25.13
    assert policy.can_view(viewer, owner, system, vis, mod) is ok


@pytest.mark.parametrize("faces,pi,nsfw,suitable,allowed,reason", [
    (False, False, False, True, True, None),
    (True, False, False, True, False, "faces"),
    (False, True, False, True, False, "personal_info"),
    (False, False, True, True, False, "unsuitable"),
    (False, False, False, False, False, "unsuitable"),
    (True, True, False, True, False, "faces"),
])
def test_share_decision(faces, pi, nsfw, suitable, allowed, reason):  # TC-25.19
    d = policy.share_decision(faces, pi, nsfw, suitable)
    assert d.allowed is allowed and d.reason == reason
    assert d.moderation_status == ("approved" if allowed else "rejected")
