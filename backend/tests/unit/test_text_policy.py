"""unsafe_text: contact info and links in free text."""
import pytest

from backend.app.services.policy import unsafe_text


@pytest.mark.parametrize("text", [
    "call 0912 345 678", "0912.345.678", "+84 (912) 345-678", "me@example.com", "http://x.y", "https://a",
    "www.foo", "visit foo.vn", "@bao_chau", "id: @minh",
])
def test_unsafe(text):
    assert unsafe_text("fine", text)


@pytest.mark.parametrize("text", ["coffee cup", "Lớp 7A, 12 học sinh", "room 1234567", "", None, "e.g. a cat"])
def test_safe(text):
    assert not unsafe_text(text)
