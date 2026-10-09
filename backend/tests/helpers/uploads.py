"""Upload/card helpers for API tests."""
from __future__ import annotations


def upload(api, data: bytes, name: str = "x.jpg", ctype: str = "image/jpeg"):
    return api.post("/api/uploads", files={"file": (name, data, ctype)})


def ready_content(api, data: bytes) -> dict:
    r = upload(api, data)
    assert r.status_code == 202, r.text
    s = api.get(f"/api/uploads/{r.json()['content_id']}")
    assert s.status_code == 200 and s.json()["status"] == "ready", s.text
    return s.json()


def make_card(api, data: bytes, **body) -> dict:
    c = ready_content(api, data)
    r = api.post("/api/cards", json={"content_id": c["content_id"], **body})
    assert r.status_code in (200, 201), r.text
    return r.json()
