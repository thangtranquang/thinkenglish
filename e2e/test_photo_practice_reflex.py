"""Add-photo -> Review -> save -> Practice, Practice levels open, Reflex session and the self-check fallback."""
import io
import random

from PIL import Image
from playwright.sync_api import expect

from flows import first_card_id, goto_hash, hold_to_talk, register_via_camera_gate, unique_nick


def photo(seed: int) -> dict:
    rnd = random.Random(seed)
    img = Image.new("RGB", (96, 64), (rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)))
    for _ in range(40):
        img.putpixel((rnd.randrange(96), rnd.randrange(64)), (rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return {"name": "photo.jpg", "mimeType": "image/jpeg", "buffer": buf.getvalue()}


def test_upload_review_save_practice_and_dedupe(new_context):
    seed = random.randrange(10**9)
    page = new_context().new_page()
    register_via_camera_gate(page, unique_nick("photo"))

    page.get_by_test_id("addphoto-file").set_input_files(photo(seed))
    expect(page.get_by_test_id("addphoto-ai-calls")).to_have_text("1")
    expect(page.get_by_test_id("screen-review")).to_be_visible()  # opened automatically when ready

    labels = page.get_by_test_id("review-label-input")
    assert labels.count() >= 2
    marker = page.get_by_test_id("marker").first
    before = marker.get_attribute("style")
    box = marker.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] / 2 + 25, box["y"] + box["height"] / 2 + 15, steps=4)
    page.mouse.up()
    assert marker.get_attribute("style") != before  # the marker moved
    labels.first.fill("my renamed word")
    total = labels.count()
    page.get_by_test_id("review-label-delete").last.click()
    expect(page.get_by_test_id("review-label-input")).to_have_count(total - 1)
    page.get_by_test_id("review-title").fill("Góc học của tôi")
    expect(page.get_by_test_id("review-vis-private")).to_be_checked()  # private by default
    page.get_by_test_id("review-save").click()
    expect(page.get_by_test_id("review-saved")).to_contain_text("Góc học của tôi")

    page.get_by_test_id("review-share").click()  # either shared, or refused with a Vietnamese message
    page.wait_for_timeout(500)

    page.get_by_test_id("review-practice").click()
    expect(page.get_by_test_id("practice-record")).to_be_visible()
    expect(page.get_by_test_id("practice-line").first).to_contain_text("my renamed word")
    hold_to_talk(page, "my renamed word")
    expect(page.get_by_test_id("practice-feedback")).to_contain_text("Chính xác 100%")

    # the same image uploaded by someone else costs no AI call
    other = new_context().new_page()
    register_via_camera_gate(other, unique_nick("photo2"))
    other.get_by_test_id("addphoto-file").set_input_files(photo(seed))
    expect(other.get_by_test_id("addphoto-status")).to_contain_text("không tốn lượt AI")
    expect(other.get_by_test_id("addphoto-ai-calls")).to_have_text("1")  # still the single original call


def test_addphoto_rejects_wrong_type_on_the_client(new_context):
    page = new_context().new_page()
    register_via_camera_gate(page, unique_nick("badfile"))
    page.get_by_test_id("addphoto-file").set_input_files({"name": "a.gif", "mimeType": "image/gif", "buffer": b"GIF89a"})
    expect(page.get_by_test_id("addphoto-error")).to_contain_text("JPEG, PNG hoặc WebP")


def test_practice_levels_two_and_three_are_open_from_the_start(new_context):
    page = new_context().new_page()
    register_via_camera_gate(page, unique_nick("prac"))
    goto_hash(page, "#/home")
    card_id = first_card_id(page)
    words = page.evaluate("id => fetch('/api/cards/' + id).then(r => r.json()).then(c => c.labels.map(l => l.word))", card_id)
    goto_hash(page, "#/practice/" + card_id)
    expect(page.get_by_test_id("practice-tab-2")).to_be_enabled()
    expect(page.get_by_test_id("practice-tab-3")).to_be_enabled()
    for i, word in enumerate(words):
        page.get_by_test_id("practice-line").nth(i).click()
        hold_to_talk(page, word)
        expect(page.get_by_test_id("practice-feedback")).to_contain_text("Chính xác 100%")
        page.wait_for_timeout(300)
    expect(page.get_by_test_id("practice-tab-2")).to_be_enabled()
    page.get_by_test_id("practice-tab-2").click()
    expect(page.get_by_test_id("practice-line").first).to_be_visible()
    page.get_by_test_id("practice-vi-toggle").first.click()
    expect(page.get_by_test_id("practice-vi-toggle").first).to_have_text("Ẩn nghĩa")


def test_practice_self_check_when_recognition_is_missing(new_context):
    ctx = new_context()
    ctx.add_init_script("delete window.SpeechRecognition; delete window.webkitSpeechRecognition;")
    page = ctx.new_page()
    page.goto("/")
    goto_hash(page, "#/practice/" + first_card_id(page))
    hold_to_talk(page, "")
    expect(page.get_by_test_id("practice-selfcheck")).to_contain_text("Tự đánh giá")
    page.get_by_test_id("practice-selfcheck-ok").click()
    expect(page.get_by_test_id("practice-feedback")).to_contain_text("Chính xác 100%")


def test_reflex_session_runs_to_summary(new_context):
    page = new_context().new_page()
    register_via_camera_gate(page, unique_nick("reflex"))
    goto_hash(page, "#/reflex")
    expect(page.get_by_test_id("reflex-level-2")).to_be_disabled()  # only R1 is open at first
    page.get_by_test_id("reflex-start").click()
    expect(page.get_by_test_id("reflex-round")).to_be_visible()
    rounds = page.evaluate("() => window.__rounds.length")
    for i in range(rounds):
        expect(page.get_by_test_id("reflex-round")).to_contain_text(f"Vòng {i + 1}/{rounds}")
        expect(page.get_by_test_id("reflex-reveal")).to_be_visible(timeout=15000)
        assert int(page.get_by_test_id("reflex-score").inner_text()) >= 70  # said the right word fast
        page.get_by_test_id("reflex-next").click()
    expect(page.get_by_test_id("reflex-summary")).to_be_visible()
    expect(page.get_by_test_id("summary-score")).not_to_have_text("—")
