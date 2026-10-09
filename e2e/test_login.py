"""TC-11.2 + TC-12.2: a returning user logs in on a new device that already has guest progress."""
from playwright.sync_api import expect

from flows import PASSWORD, first_card_id, goto_hash, hold_to_talk, register_via_camera_gate, unique_nick


def test_login_on_new_device_discards_guest_progress(new_context):
    nick = unique_nick("login")
    page_a = new_context().new_page()
    register_via_camera_gate(page_a, nick)

    page_b = new_context().new_page()
    page_b.goto("/")
    goto_hash(page_b, "#/practice/" + first_card_id(page_b))
    hold_to_talk(page_b, "coffee cup")
    expect(page_b.get_by_test_id("practice-feedback")).to_contain_text("Chính xác")  # this guest has progress

    goto_hash(page_b, "#/login")
    page_b.get_by_test_id("login-nickname").fill(nick)
    page_b.get_by_test_id("login-password").fill(PASSWORD)
    page_b.get_by_test_id("login-submit").click()

    expect(page_b.get_by_test_id("discard-dialog")).to_be_visible()
    page_b.get_by_test_id("discard-dialog-ok").click()
    expect(page_b.get_by_test_id("home-reflex")).to_be_visible()
    expect(page_b.get_by_text("Xin chào, " + nick)).to_be_visible()
    me = page_b.evaluate("fetch('/api/me').then(r => r.json())")
    assert me["user"]["nickname"] == nick and me["is_guest"] is False
    assert me["user"]["xp"] == 0  # the guest progress was discarded, not merged
