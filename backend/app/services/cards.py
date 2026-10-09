"""Card business rules: visibility, label merging, create/save/share/delete."""
from __future__ import annotations

import json
import sqlite3
import uuid

from ..clock import Clock, iso
from ..errors import AppError
from ..repositories import cards as repo
from ..repositories import content as content_repo
from ..repositories import practice as practice_repo
from ..schemas.cards import CardCreateIn
from . import policy, stats, validators

NOT_FOUND = (404, "not_found")
SHARE_MESSAGES = {
    "faces": "Ảnh có khuôn mặt nhận diện được nên không thể chia sẻ công khai.",
    "personal_info": "Ảnh có thông tin cá nhân nên không thể chia sẻ công khai.",
    "unsuitable": "Ảnh không phù hợp với học sinh nên không thể chia sẻ công khai.",
    "text": "Tiêu đề hoặc từ vựng có thông tin liên lạc hoặc liên kết nên không thể chia sẻ công khai.",
}


def _audio(name: str | None) -> str | None:
    return f"/audio/{name}" if name else None


def image_url(card_id: str) -> str:
    return f"/api/cards/{card_id}/image"


def mastery_for(conn: sqlite3.Connection, user_id: str, card_ids: list[str]) -> dict[str, int | None]:
    """Mean of the last <= 5 attempt scores per card (0-100); None when the user has no attempts."""
    scores = practice_repo.card_scores(conn, user_id, card_ids)
    out: dict[str, int | None] = {}
    for cid in card_ids:
        mean = stats.mastery_mean(scores.get(cid, []))
        out[cid] = None if mean is None else round(mean)
    return out


def merged_labels(base: list[dict], overrides_json: str | None) -> list[dict]:
    """Content labels with the card's overrides applied (edit/move/delete existing labels only)."""
    if not overrides_json:
        return base
    by_id = {lab["id"]: lab for lab in base}
    out = []
    for ov in json.loads(overrides_json):
        lab = by_id.get(ov["id"])
        if lab is None:
            continue
        merged = dict(lab, x=ov["x"], y=ov["y"])
        if ov["word"].strip().lower() != lab["word"].lower():
            merged.update(word=ov["word"].strip(), ipa=None, audio_file=None, accepted_answers="[]")
        else:
            merged["word"] = ov["word"].strip()
        out.append(merged)
    return out


def label_detail(lab: dict) -> dict:
    return {"id": lab["id"], "word": lab["word"], "ipa": lab["ipa"], "vi_meaning": lab["vi_meaning"],
            "x": lab["x"], "y": lab["y"], "accepted_answers": json.loads(lab["accepted_answers"] or "[]"),
            "audio_url": _audio(lab["audio_file"])}


def sentence_out(s: dict) -> dict:
    return {"id": s["id"], "kind": s["kind"], "en": s["en"], "vi": s["vi"], "audio_url": _audio(s["audio_file"])}


def visible_card(conn: sqlite3.Connection, viewer_id: str, card_id: str) -> dict:
    row = repo.get_card(conn, card_id, viewer_id)
    if row is None or not policy.can_view(viewer_id, row["owner_id"], row["owner_kind"] == "system",
                                          row["visibility"], row["moderation_status"]):
        raise AppError(*NOT_FOUND)
    return row


def owned_card(conn: sqlite3.Connection, user_id: str, card_id: str) -> dict:
    row = repo.get_card(conn, card_id, user_id)
    if row is None or row["owner_id"] != user_id:
        raise AppError(*NOT_FOUND)
    return row


def detail(conn: sqlite3.Connection, viewer_id: str, row: dict) -> dict:
    labels = content_repo.labels_for(conn, [row["content_id"]])[row["content_id"]]
    return {
        "id": row["id"], "title": row["title"], "topic": row["topic"], "cefr_level": row["cefr_level"],
        "visibility": row["visibility"], "owner_nickname": row["owner_nickname"],
        "is_mine": row["owner_id"] == viewer_id, "saved": bool(row["saved"]),
        "mastery": mastery_for(conn, viewer_id, [row["id"]])[row["id"]], "image_url": image_url(row["id"]),
        "unlocked_levels": practice_repo.unlocked_levels(conn, viewer_id, row["id"]),
        "labels": [label_detail(lab) for lab in merged_labels(labels, row["label_overrides"])],
        "sentences": [sentence_out(s) for s in content_repo.sentences_for(conn, row["content_id"])],
    }


def get_detail(conn: sqlite3.Connection, viewer_id: str, card_id: str) -> dict:
    return detail(conn, viewer_id, visible_card(conn, viewer_id, card_id))


def list_page(conn: sqlite3.Connection, clock: Clock, viewer_id: str, scope: str, topic: str | None,
              cefr: str | None, q: str | None, offset: int, limit: int) -> dict:
    rows = repo.list_cards(conn, viewer_id, scope, topic, cefr, (q or "").strip() or None, offset, limit + 1,
                           iso(clock.now()))
    has_more, rows = len(rows) > limit, rows[:limit]
    labels = content_repo.labels_for(conn, list({r["content_id"] for r in rows}))
    mastery = mastery_for(conn, viewer_id, [r["id"] for r in rows])
    items = [{
        "id": r["id"], "title": r["title"], "topic": r["topic"],
        "labels": [{"word": lab["word"], "ipa": lab["ipa"], "audio_url": _audio(lab["audio_file"])}
                   for lab in merged_labels(labels[r["content_id"]], r["label_overrides"])],
        "mastery": mastery[r["id"]], "image_url": image_url(r["id"]), "owner_nickname": r["owner_nickname"],
        "saved": bool(r["saved"]), "is_mine": r["owner_id"] == viewer_id,
    } for r in rows]
    return {"items": items, "has_more": has_more}


def topics(conn: sqlite3.Connection) -> dict:
    return {"items": repo.topic_counts(conn)}


def create_card(conn: sqlite3.Connection, clock: Clock, user_id: str, body: CardCreateIn) -> tuple[dict, bool]:
    """Returns (detail, created). Idempotent via UNIQUE(owner, content). Needs an upload claim."""
    content_id = str(body.content_id)
    content = content_repo.get_content(conn, content_id)
    if content is None or not content_repo.claim_exists(conn, user_id, content_id):
        raise AppError(*NOT_FOUND)
    if content["status"] != "ready":
        raise AppError(409, "not_ready")
    labels = content_repo.labels_for(conn, [content_id])[content_id]
    overrides = [o.model_dump() for o in body.label_overrides] if body.label_overrides is not None else None
    title = (body.title or "").strip() or content["topic"] or "Thẻ mới"
    try:
        validators.validate_review_overrides({lab["id"] for lab in labels}, title,
                                             overrides if overrides is not None else [{"id": lab["id"], "word": lab["word"], "x": lab["x"], "y": lab["y"]} for lab in labels])
    except validators.ValidationFailure as exc:
        raise AppError(422, "validation_error", fields={"label_overrides": exc.code}) from None
    if overrides is not None:
        for o in overrides:
            o["word"] = o["word"].strip()
    card_id = str(uuid.uuid4())
    created = repo.insert_card(conn, card_id, user_id, content_id, title,
                               json.dumps(overrides, ensure_ascii=False) if overrides is not None else None,
                               iso(clock.now()))
    if not created:
        card_id = repo.find_by_owner_content(conn, user_id, content_id)
    return detail(conn, user_id, repo.get_card(conn, card_id, user_id)), created


def save(conn: sqlite3.Connection, clock: Clock, user_id: str, card_id: str) -> None:
    row = visible_card(conn, user_id, card_id)
    if row["owner_id"] != user_id:
        repo.add_save(conn, user_id, card_id, iso(clock.now()))


def unsave(conn: sqlite3.Connection, user_id: str, card_id: str) -> None:
    visible_card(conn, user_id, card_id)
    repo.remove_save(conn, user_id, card_id)


def share(conn: sqlite3.Connection, clock: Clock, user_id: str, card_id: str) -> dict:
    row = owned_card(conn, user_id, card_id)
    if row["moderation_status"] != "approved":
        safety = json.loads(row["safety"] or "{}")
        decision = policy.share_decision(bool(safety.get("faces")), bool(safety.get("personal_info")),
                                         bool(safety.get("unsuitable")), True)
        reason = decision.reason or "unsuitable"
        raise AppError(422, "share_not_allowed", reason=reason, fields={"message": SHARE_MESSAGES[reason]})
    labels = content_repo.labels_for(conn, [row["content_id"]])[row["content_id"]]
    if policy.unsafe_text(row["title"], *(lab["word"] for lab in merged_labels(labels, row["label_overrides"]))):
        raise AppError(422, "share_not_allowed", reason="text", fields={"message": SHARE_MESSAGES["text"]})
    if row["visibility"] != "public":
        repo.set_visibility(conn, card_id, "public", iso(clock.now()))
    return detail(conn, user_id, repo.get_card(conn, card_id, user_id))


def unshare(conn: sqlite3.Connection, user_id: str, card_id: str) -> dict:
    owned_card(conn, user_id, card_id)
    repo.set_visibility(conn, card_id, "private", None)
    repo.remove_other_saves(conn, card_id, user_id)
    return detail(conn, user_id, repo.get_card(conn, card_id, user_id))


def delete(conn: sqlite3.Connection, user_id: str, card_id: str) -> None:
    owned_card(conn, user_id, card_id)
    repo.delete_card(conn, card_id)
