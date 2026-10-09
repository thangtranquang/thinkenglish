"""TC-31.1: hands-free auto mode runs from a single tap, posts attempts, can be stopped and pauses when hidden."""
from playwright.sync_api import expect

from flows import goto_hash, register_via_camera_gate, unique_nick


def _is_attempt(r):
    return r.url.endswith("/api/attempts") and r.request.method == "POST"


def _start_auto(page):
    register_via_camera_gate(page, unique_nick("auto"))
    goto_hash(page, "#/reflex")
    with page.expect_response(_is_attempt) as first:
        page.get_by_test_id("auto-start").click()  # the only tap
        expect(page.get_by_test_id("auto-stop")).to_be_visible()
    return first.value


def test_auto_mode_one_tap_posts_attempt_and_stop_works(page):
    attempts = []
    page.on("request", lambda r: attempts.append(r) if r.url.endswith("/api/attempts") and r.method == "POST" else None)
    resp = _start_auto(page)
    assert resp.status == 201
    body = resp.request.post_data_json
    assert body["mode"] == "auto" and body["transcript"]
    assert resp.json()["accuracy"] == 100  # the stub said the word shown on screen

    page.get_by_test_id("auto-stop").click()
    expect(page.get_by_test_id("reflex-start")).to_be_visible()
    count = len(attempts)
    page.wait_for_timeout(4500)
    assert len(attempts) == count, "auto mode kept posting after Stop"


def test_auto_mode_pauses_when_the_tab_is_hidden(page):
    _start_auto(page)
    hide = "() => { Object.defineProperty(document, 'hidden', { configurable: true, get: () => %s }); document.dispatchEvent(new Event('visibilitychange')); }"
    page.evaluate(hide % "true")
    expect(page.get_by_test_id("auto-status")).to_contain_text("tạm dừng")
    posted = []
    page.on("request", lambda r: posted.append(r) if r.url.endswith("/api/attempts") else None)
    page.wait_for_timeout(4000)
    assert not posted, "an attempt was posted while paused"
    with page.expect_response(_is_attempt):
        page.evaluate(hide % "false")
    page.get_by_test_id("auto-stop").click()
