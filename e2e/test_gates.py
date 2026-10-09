"""TC-4.2: after one write session and an idle gap, the next visit shows the mandatory registration gate."""
from playwright.sync_api import expect

from flows import first_card_id, goto_hash, hold_to_talk, register_from_gate, unique_nick


def test_second_visit_gate_is_mandatory_and_register_clears_it(page):
    page.goto("/")
    goto_hash(page, "#/practice/" + first_card_id(page))
    hold_to_talk(page, "coffee cup")
    expect(page.get_by_test_id("practice-feedback")).to_contain_text("Chính xác")  # the write happened

    page.wait_for_timeout(3600)  # > SESSION_IDLE_SECONDS=3
    page.reload()

    expect(page.get_by_test_id("gate-second-visit")).to_be_visible()
    expect(page.get_by_test_id("gate-back")).to_have_count(0)  # no escape
    expect(page.locator("nav#nav")).to_be_hidden()
    goto_hash(page, "#/home")
    expect(page.get_by_test_id("gate-second-visit")).to_be_visible()  # navigation cannot leave the gate

    page.get_by_test_id("gate-register").click()
    register_from_gate(page, unique_nick("gate"))
    expect(page.get_by_test_id("home-reflex")).to_be_visible()
    expect(page.get_by_test_id("gate-second-visit")).to_have_count(0)
    page.reload()
    expect(page.get_by_test_id("home-reflex")).to_be_visible()  # still not gated after a reload
