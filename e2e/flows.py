"""Small UI flows shared by the e2e specs."""
import time
from datetime import datetime


def adult_year() -> str:
    return str(datetime.now().year - 20)


def unique_nick(prefix: str = "hs") -> str:
    return f"{prefix}_{int(time.time() * 1000) % 10**9}"


PASSWORD = "pass-word-1"


def register_from_gate(page, nickname: str, password: str = PASSWORD) -> None:
    """On the register screen (reached from any gate): fill the form as an adult and submit."""
    page.get_by_test_id("register-nickname").fill(nickname)
    page.get_by_test_id("register-password").fill(password)
    page.get_by_test_id("register-year").select_option(adult_year())
    page.get_by_test_id("register-submit").click()


def goto_hash(page, hash_: str) -> None:
    """In-app navigation without a page load (keeps the in-memory session state)."""
    page.evaluate("h => { location.hash = h; }", hash_)


def first_card_id(page) -> str:
    page.wait_for_function("() => document.cookie.includes('re_csrf')")  # the session is bootstrapped
    return page.evaluate("fetch('/api/cards?scope=explore&limit=1').then(r => r.json()).then(j => j.items[0].id)")


def hold_to_talk(page, text: str, hold_ms: int = 700) -> None:
    """Press and hold the practice record button while the recognition stub answers `text`."""
    page.evaluate("t => { window.__stt.text = t; }", text)
    btn = page.get_by_test_id("practice-record")
    btn.scroll_into_view_if_needed()
    box = btn.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.wait_for_timeout(hold_ms)
    page.mouse.up()


def register_via_camera_gate(page, nickname: str) -> None:
    """Guest on Home -> camera -> gate -> register; ends on the Add-photo screen."""
    page.goto("/")
    page.get_by_test_id("home-camera").click()
    page.get_by_test_id("gate-register").click()
    register_from_gate(page, nickname)
    page.get_by_test_id("addphoto-file").wait_for(state="attached")
