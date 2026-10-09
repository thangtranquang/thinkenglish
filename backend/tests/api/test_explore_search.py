"""TC-26.1 and listing validation."""
import pytest

from backend.tests.helpers.images import jpeg_bytes
from backend.tests.helpers.uploads import make_card


def test_topics_and_filters(reg):
    topics = reg.get("/api/topics").json()["items"]
    assert sum(t["count"] for t in topics) == 12
    seed_topic = topics[0]["name"]
    r = reg.get("/api/cards", params={"scope": "explore", "topic": seed_topic.lower(), "limit": 20}).json()
    assert r["has_more"] is False and r["items"]
    assert all(i["topic"] == seed_topic for i in r["items"])
    it = r["items"][0]
    assert set(it) == {"id", "title", "topic", "labels", "mastery", "image_url", "owner_nickname", "saved",
                       "is_mine"}
    assert set(it["labels"][0]) == {"word", "ipa", "audio_url"}
    card = make_card(reg, jpeg_bytes(31))
    ids = [i["id"] for i in reg.get("/api/cards", params={"scope": "explore", "limit": 50}).json()["items"]]
    assert card["id"] not in ids
    assert [i["id"] for i in reg.get("/api/cards", params={"scope": "mine"}).json()["items"]] == [card["id"]]


def test_pagination_and_search(reg):
    page = reg.get("/api/cards", params={"limit": 3}).json()
    assert len(page["items"]) == 3 and page["has_more"] is True
    rest = reg.get("/api/cards", params={"limit": 3, "offset": 9}).json()
    assert len(rest["items"]) == 3 and rest["has_more"] is False
    word = page["items"][0]["labels"][0]["word"]
    found = reg.get("/api/cards", params={"q": word[:3]}).json()["items"]
    assert any(i["id"] == page["items"][0]["id"] for i in found)
    assert reg.get("/api/cards", params={"q": "%"}).json()["items"] == []


@pytest.mark.parametrize("params", [{"scope": "x"}, {"limit": 0}, {"limit": 51}, {"offset": -1}, {"q": "a" * 61}])
def test_invalid_query_rejected(reg, params):
    assert reg.get("/api/cards", params=params).status_code == 422


def test_save_unsave(reg):
    cid = reg.get("/api/cards").json()["items"][0]["id"]
    assert reg.post(f"/api/cards/{cid}/save").status_code == 204
    assert [i["id"] for i in reg.get("/api/cards", params={"scope": "saved"}).json()["items"]] == [cid]
    assert reg.get(f"/api/cards/{cid}").json()["saved"] is True
    assert reg.delete(f"/api/cards/{cid}/save").status_code == 204
    assert reg.get("/api/cards", params={"scope": "saved"}).json()["items"] == []
