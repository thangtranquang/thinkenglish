"""TC-29.4: reflex sessions, server-side reflex score, simplified unlock, owner-only completion."""
from backend.tests.helpers.practice import att


def _post_round(api, session, r, ms, level=1):
    body = att(r["item_id"], r["word"], mode="reflex", reflex_level=level, reflex_ms=ms,
               reflex_session_id=session["session_id"])
    body["card_id"] = r["card_id"]
    return api.post("/api/attempts", json=body)


def test_complete_session_scores_and_unlocks(guest, new_api):  # TC-29.4
    s = guest.post("/api/reflex/sessions", json={"level": 1})
    assert s.status_code == 201
    session = s.json()
    assert 5 <= len(session["rounds"]) <= 10 and session["limit_ms"] == 6000
    for r in session["rounds"][:5]:
        resp = _post_round(guest, session, r, 1500)
        assert resp.status_code == 201, resp.text
        assert resp.json()["score"] == 96 and resp.json()["accuracy"] == 100  # 0.6*100 + 0.4*90
    done = guest.post(f"/api/reflex/sessions/{session['session_id']}/complete")
    assert done.status_code == 200
    body = done.json()
    assert (body["score"], body["answered"], body["counted"], body["reflex_level_unlocked"]) == (96, 5, True, 2)
    assert guest.post(f"/api/reflex/sessions/{session['session_id']}/complete").json() == body  # idempotent
    assert new_api().post(f"/api/reflex/sessions/{session['session_id']}/complete").status_code == 404
    assert guest.post("/api/reflex/sessions", json={"level": 2}).status_code == 201
    assert guest.post("/api/reflex/sessions", json={"level": 3}).status_code == 409


def test_timeout_and_out_of_range(guest):
    r = guest.post("/api/reflex/sessions", json={"level": 1}).json()
    session, first = r, r["rounds"][0]
    t = _post_round(guest, session, first, 7000)  # limit 6000 -> timeout inside the 2000 ms grace
    assert t.status_code == 201 and t.json()["timeout"] and t.json()["score"] == 0 and t.json()["accuracy"] == 0
    assert _post_round(guest, session, first, 8001).status_code == 422
    assert _post_round(guest, session, first, -1).status_code == 422
    assert guest.post("/api/reflex/sessions", json={"level": 5}).status_code == 422
