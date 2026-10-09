"""Seed content sanity: illustrations exist, label geometry is valid, audio files are present."""
import json
import re

import pytest

from backend.app.seed import SEED_ASSETS, SEED_DATA, audio_name

CARDS = json.loads(SEED_DATA.read_text(encoding="utf-8"))["cards"]
AUDIO_DIR = SEED_ASSETS.parents[1] / "frontend" / "audio"
MAX_WORDS = 12


def _sentences(card):
    texts = [s["en"] for s in card["descriptions"]]
    texts += [t for t in re.split(r"(?<=[.!?])\s+", card["story"]["en"]) if t]
    return texts


def test_card_keys_unique_and_topic_count():
    keys = [c["seed_key"] for c in CARDS]
    assert len(keys) == len(set(keys)) == 12
    assert len({c["topic"] for c in CARDS}) == 8


@pytest.mark.parametrize("card", CARDS, ids=lambda c: c["seed_key"])
def test_card_has_image_and_valid_labels(card):
    assert (SEED_ASSETS / f"{card['seed_key']}.jpg").stat().st_size < 150_000
    words = [lab["word"] for lab in card["labels"]]
    assert 3 <= len(words) <= 5 and len(set(words)) == len(words)
    for lab in card["labels"]:
        x1, y1, x2, y2 = lab["box"]
        assert 0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1, lab["word"]
        assert 0 <= lab["x"] <= 1 and 0 <= lab["y"] <= 1
        assert x1 <= lab["x"] <= x2 and y1 <= lab["y"] <= y2, lab["word"]
        assert lab["accepted_answers"] and lab["word"] in lab["accepted_answers"]


@pytest.mark.parametrize("card", CARDS, ids=lambda c: c["seed_key"])
def test_sentences_are_short(card):
    assert len(card["descriptions"]) == 2
    for text in _sentences(card):
        assert len(text.split()) <= MAX_WORDS, text
    assert card["story"]["vi"] and all(s["vi"] for s in card["descriptions"])


def test_all_audio_files_exist():
    missing = []
    for card in CARDS:
        texts = [lab["word"] for lab in card["labels"]] + [s["en"] for s in card["descriptions"]] + [card["story"]["en"]]
        missing += [audio_name(t) for t in texts if not (AUDIO_DIR / audio_name(t)).exists()]
    assert not missing, f"missing audio (run tools/gen_audio.py then tools/sync_audio.py): {missing[:5]}"
