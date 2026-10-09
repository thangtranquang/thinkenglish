"""TC-40.1: a guest uses the app without signing up, hits the camera gate, comes back, registers, and stays logged in."""
from playwright.sync_api import expect

from flows import register_from_gate, unique_nick


def test_guest_to_registered(new_context):
    ctx = new_context()
    page = ctx.new_page()
    nick = unique_nick()

    page.goto("/")
    # guests can browse and look at sample cards without any signup
    expect(page.get_by_test_id("home-cards").get_by_test_id("card-tile").first).to_be_visible()
    page.get_by_test_id("nav-explore").click()
    page.get_by_test_id("card-tile").first.click()
    expect(page.get_by_test_id("detail-save")).to_be_visible()

    # camera -> gate -> Back -> camera again
    page.get_by_test_id("nav-home").click()
    page.get_by_test_id("home-camera").click()
    expect(page.get_by_test_id("gate-camera")).to_be_visible()
    page.get_by_test_id("gate-back").click()
    expect(page.get_by_test_id("home-cards")).to_be_visible()
    page.get_by_test_id("home-camera").click()
    expect(page.get_by_test_id("gate-camera")).to_be_visible()

    # register from the gate -> Add-photo
    page.get_by_test_id("gate-register").click()
    register_from_gate(page, nick)
    expect(page.get_by_test_id("addphoto-file")).to_be_attached()

    # reload keeps the session
    page.reload()
    expect(page.get_by_test_id("addphoto-file")).to_be_attached()

    # a brand-new browser context with the saved cookies/storage is still logged in
    state = ctx.storage_state()
    page2 = new_context(storage_state=state).new_page()
    page2.goto("/")
    expect(page2.get_by_text("Xin chào, " + nick)).to_be_visible()
    page2.get_by_test_id("nav-camera").click()
    expect(page2.get_by_test_id("addphoto-file")).to_be_attached()
