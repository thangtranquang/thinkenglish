"""TC-43.1 (delete) and unshare."""
from backend.tests.conftest import register_payload
from backend.tests.helpers.images import jpeg_bytes
from backend.tests.helpers.uploads import make_card


def test_unshare_removes_other_saves_and_delete_cascades(reg, new_api, db):
    cid = make_card(reg, jpeg_bytes(41))["id"]
    reg.post(f"/api/cards/{cid}/share")
    b = new_api()
    b.post("/api/auth/register", json=register_payload(nickname="Bao_Chau"))
    assert b.post(f"/api/cards/{cid}/save").status_code == 204
    assert db.execute("SELECT COUNT(*) FROM card_saves WHERE card_id = ?", (cid,)).fetchone()[0] == 1
    r = reg.delete(f"/api/cards/{cid}/share")
    assert r.status_code == 200 and r.json()["visibility"] == "private"
    assert db.execute("SELECT COUNT(*) FROM card_saves WHERE card_id = ?", (cid,)).fetchone()[0] == 0
    assert b.get(f"/api/cards/{cid}").status_code == 404
    assert reg.delete(f"/api/cards/{cid}").status_code == 204
    assert db.execute("SELECT COUNT(*) FROM cards WHERE id = ?", (cid,)).fetchone()[0] == 0
    assert reg.get(f"/api/cards/{cid}").status_code == 404
