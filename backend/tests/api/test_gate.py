"""TC-4.1 second-visit gate on bootstrap, TC-4.3 every non-exempt route is gated, TC-6.8 reason priority."""
import re

from fastapi import Depends
from fastapi.routing import APIRoute

from backend.app import deps


def test_second_visit_sets_gate(guest, clock, db, write_session):  # TC-4.1
    write_session(guest.user_id)
    clock.advance(seconds=1801)
    body = guest.bootstrap().json()
    assert body["gate"] == {"reason": "second_visit", "mandatory": True}
    assert db.execute("SELECT gate_required_at FROM users WHERE id = ?", (guest.user_id,)).fetchone()[0] is not None
    assert guest.get("/api/me").json()["gate"]["reason"] == "second_visit"  # exempt
    assert guest.post("/api/session/heartbeat").json()["gate"]["reason"] == "second_visit"


def test_no_write_means_no_gate(guest, clock):
    clock.advance(seconds=1801)
    assert guest.bootstrap().json()["gate"] is None


def _api_routes(app):
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api"):
            for method in route.methods - {"HEAD", "OPTIONS"}:
                yield method, route.path


def test_every_non_exempt_route_is_blocked_for_gated_guest(app, gated):  # TC-4.3
    routes = set(_api_routes(app))
    assert deps.GATE_EXEMPT <= routes  # the exempt list names only real routes
    for method, path in sorted(routes - deps.GATE_EXEMPT):
        r = gated._call(method, re.sub(r"\{[^}]+\}", "x", path), json={})
        assert r.status_code == 403 and r.json() == {"error": "registration_required",
                                                      "reason": "second_visit"}, (method, path, r.text)


def _probe_app(app):
    @app.post("/api/_probe/gated")
    def gated_route(user=Depends(deps.not_gated_user)):
        return {"ok": True}

    @app.post("/api/_probe/camera")
    def camera_route(user=Depends(deps.registered_user("camera"))):
        return {"ok": True}

    @app.post("/api/_probe/account")
    def account_route(user=Depends(deps.registered_user("account"))):
        return {"ok": True}

    for _ in range(3):  # routes added after the static mount would be shadowed by it
        app.router.routes.insert(0, app.router.routes.pop())


def test_guard_reasons(app, guest):
    _probe_app(app)
    assert guest.post("/api/_probe/gated").status_code == 200
    r = guest.post("/api/_probe/camera")
    assert r.status_code == 403 and r.json() == {"error": "registration_required", "reason": "camera"}
    assert guest.post("/api/_probe/account").json()["reason"] == "account"


def test_second_visit_wins_over_camera(app, gated):  # TC-6.8
    _probe_app(app)
    r = gated.post("/api/_probe/camera")
    assert r.status_code == 403 and r.json()["reason"] == "second_visit"


def test_registered_passes_all_guards(app, reg):
    _probe_app(app)
    assert reg.post("/api/_probe/camera").status_code == 200
    assert reg.post("/api/_probe/gated").status_code == 200
