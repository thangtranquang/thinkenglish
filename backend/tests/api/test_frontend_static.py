"""Frontend shell is served statically and never uses innerHTML (slice 5)."""
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[3] / "frontend"
JS_FILES = sorted((FRONTEND / "js").rglob("*.js"))


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "app.css" in r.text and "js/main.js" in r.text
    assert client.get("/css/app.css").status_code == 200


def test_every_js_module_served_and_present():
    names = {p.name for p in JS_FILES}
    required = {"main.js", "api.js", "state.js", "router.js", "ui.js", "home.js", "gate.js",
                "register.js", "login.js", "explore.js", "library.js", "profile.js",
                "practice.js", "reflex.js", "addphoto.js", "review.js"}
    assert required <= names


def test_js_files_return_200(client):
    assert JS_FILES, "no frontend js files"
    for p in JS_FILES:
        rel = p.relative_to(FRONTEND).as_posix()
        assert client.get("/" + rel).status_code == 200, rel


def test_no_inner_html_in_js():
    for p in JS_FILES:
        assert "innerHTML" not in p.read_text(encoding="utf-8"), p.name
