"""TC-25.1, 25.2, 25.4."""
import hashlib

import pytest

from backend.app.ai.mock import MockProvider
from backend.tests.conftest import register_payload
from backend.tests.helpers.images import jpeg_bytes
from backend.tests.helpers.uploads import make_card


@pytest.fixture
def other(new_api):
    b = new_api()
    assert b.post("/api/auth/register", json=register_payload(nickname="Bao_Chau")).status_code == 201
    return b


@pytest.fixture
def guest_api(new_api):
    return new_api()


def _seed_id(db):
    return db.execute("SELECT c.id FROM cards c JOIN card_contents cc ON cc.id = c.content_id "
                      "WHERE cc.seed_key IS NOT NULL LIMIT 1").fetchone()[0]


def test_private_image_visibility(reg, other, guest_api, db):
    card = make_card(reg, jpeg_bytes(21))
    url = f"/api/cards/{card['id']}/image"
    assert reg.get(url).status_code == 200
    assert other.get(url).status_code == 404
    assert guest_api.get(url).status_code == 404
    seed = f"/api/cards/{_seed_id(db)}/image"
    for who in (reg, other, guest_api):
        assert who.get(seed).status_code == 200


def test_all_subroutes_404_for_non_owner(reg, other, guest_api):
    cid = make_card(reg, jpeg_bytes(22))["id"]
    for method, path in [("get", ""), ("get", "/image"), ("post", "/save"), ("post", "/share"),
                         ("delete", "/share"), ("delete", "")]:
        r = getattr(other, method)(f"/api/cards/{cid}{path}")
        assert r.status_code == 404, (method, path)
    assert guest_api.get(f"/api/cards/{cid}").status_code == 404
    assert guest_api.post(f"/api/cards/{cid}/save").status_code == 404
    assert guest_api.post(f"/api/cards/{cid}/share").status_code == 403


def test_share_makes_public_and_faces_rejected(reg, other, app, db):
    cid = make_card(reg, jpeg_bytes(23))["id"]
    r = reg.post(f"/api/cards/{cid}/share")
    assert r.status_code == 200 and r.json()["visibility"] == "public"
    assert other.get(f"/api/cards/{cid}").status_code == 200

    def faces(n, data):
        res = MockProvider._build(hashlib.sha256(data).digest())
        res.safety.has_identifiable_faces = True
        return res
    app.state.provider = MockProvider(script=faces)
    cid2 = make_card(reg, jpeg_bytes(24))["id"]
    r = reg.post(f"/api/cards/{cid2}/share")
    assert r.status_code == 422 and r.json()["error"] == "share_not_allowed" and r.json()["reason"] == "faces"
    assert r.json()["fields"]["message"]
    row = db.execute("SELECT cc.moderation_status, c.visibility FROM cards c JOIN card_contents cc "
                     "ON cc.id = c.content_id WHERE c.id = ?", (cid2,)).fetchone()
    assert tuple(row) == ("rejected", "private")
