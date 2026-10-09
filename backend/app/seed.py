"""Idempotent seed of the system user and the prototype cards (ids = uuid5 of the seed key)."""
import hashlib
import io
import json
import re
import shutil
import sqlite3
import uuid
from pathlib import Path

from PIL import Image, ImageDraw

from .clock import Clock, iso
from .config import Settings
from .db import transaction
from .repositories import seed as repo

SEED_NAMESPACE = uuid.UUID("5f1c2a7e-3b64-4c58-9d0a-6e8f7a1b2c3d")
SEED_DATA = Path(__file__).resolve().with_name("seed_data.json")
SEED_ASSETS = Path(__file__).resolve().parents[1] / "seed_assets"
SYSTEM_USER_ID = str(uuid.uuid5(SEED_NAMESPACE, "system-user"))


def seed_id(*parts: str | int) -> str:
    return str(uuid.uuid5(SEED_NAMESPACE, ":".join(str(p) for p in parts)))


def _djb2(text: str) -> str:
    h = 5381
    for ch in text:
        h = (h * 33 + ord(ch)) & 0xFFFFFFFF
    return format(h, "x")


def audio_name(text: str) -> str:
    """Same file naming as tools/gen_audio.py: slug (<=40 chars) + djb2 hash."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]
    return f"{slug}-{_djb2(text)}.mp3"


def _placeholder_jpeg(seed_key: str, title: str) -> bytes:
    digest = hashlib.sha256(seed_key.encode()).digest()
    color = (80 + digest[0] % 120, 80 + digest[1] % 120, 80 + digest[2] % 120)
    img = Image.new("RGB", (800, 600), color)
    ImageDraw.Draw(img).text((40, 40), f"ReflexEnglish seed {seed_key}", fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    return buf.getvalue()


def _ensure_image(settings: Settings, seed_key: str, title: str) -> tuple[bytes, str]:
    """Return (bytes, relative storage path), copying a real seed asset or generating a placeholder."""
    rel = f"seed/{seed_key}.jpg"
    target = settings.data_dir / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    source = SEED_ASSETS / f"{seed_key}.jpg"
    if source.exists():  # refresh: an already seeded database gets the newer illustration
        if not target.exists() or target.read_bytes() != source.read_bytes():
            shutil.copyfile(source, target)
    elif not target.exists():
        target.write_bytes(_placeholder_jpeg(seed_key, title))
    return target.read_bytes(), rel


def seed_all(conn: sqlite3.Connection, settings: Settings, clock: Clock) -> None:
    data = json.loads(SEED_DATA.read_text(encoding="utf-8"))
    now = iso(clock.now())
    with transaction(conn):
        repo.upsert_system_user(conn, SYSTEM_USER_ID, "ReflexEnglish", now)
        for card in data["cards"]:
            key = card["seed_key"]
            raw, rel = _ensure_image(settings, key, card["title"])
            with Image.open(io.BytesIO(raw)) as im:
                width, height = im.size
            image_id, content_id = seed_id(key, "image"), seed_id(key, "content")
            repo.upsert_image(conn, image_id, hashlib.sha256(raw).hexdigest(), rel, width, height, now)
            cefr = card.get("cefr_level", "A1")
            repo.upsert_content(conn, content_id, image_id, key, card["topic"], cefr, now)
            for i, lab in enumerate(card["labels"]):
                repo.upsert_label(conn, seed_id(key, "label", i), content_id, i, lab["word"], lab["ipa"],
                                  lab["vi_meaning"], lab["accepted_answers"], lab["x"], lab["y"],
                                  tuple(lab["box"]) if lab.get("box") else None, cefr, audio_name(lab["word"]))
            sentences = [("description", i, s) for i, s in enumerate(card["descriptions"])]
            sentences.append(("story", 0, card["story"]))
            for kind, pos, s in sentences:
                repo.upsert_sentence(conn, seed_id(key, "sentence", kind, pos), content_id, kind, pos,
                                     s["en"], s["vi"], audio_name(s["en"]))
            repo.upsert_card(conn, seed_id(key, "card"), SYSTEM_USER_ID, content_id, card["title"], now)
