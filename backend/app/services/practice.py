"""Attempts (server-side scoring, SM-2, practice unlocks), reflex sessions and profile stats."""
from __future__ import annotations

import json
import sqlite3
import uuid

from ..clock import Clock, iso
from ..db import transaction
from ..errors import AppError
from ..repositories import practice as repo
from ..repositories import users as users_repo
from ..schemas.practice import AttemptIn, AttemptOut
from ..security import parse_iso
from . import policy, scoring, srs, stats

ITEM_LEVEL = {"label": 1, "sentence": 2, "story": 3}
REFLEX_ROUNDS = 10


def _out(row: dict, unlocked: list[int]) -> AttemptOut:
    score = row["reflex_score"] if row["reflex_score"] is not None else (row["accuracy"] or 0)
    timeout = bool(row["reflex_ms"] is not None and row["reflex_level"]
                   and scoring.is_timeout(row["reflex_ms"], scoring.LEVEL_LIMITS_MS[row["reflex_level"]]))
    return AttemptOut(id=row["id"], client_attempt_id=row["client_attempt_id"], accuracy=row["accuracy"] or 0,
                      score=score, q=srs.quality_from_score(score), xp=row["xp"], timeout=timeout,
                      unlocked_levels=unlocked)


def _targets(conn: sqlite3.Connection, card: dict, data: AttemptIn) -> list[str]:
    if data.item_type == "label":
        item = repo.label_item(conn, card["content_id"], data.item_id)
        if item is None:
            raise AppError(404, "not_found")
        return [item["word"], *json.loads(item["accepted_answers"] or "[]")]
    kind = "description" if data.item_type == "sentence" else "story"
    sent = repo.sentence_item(conn, card["content_id"], data.item_id, kind)
    if sent is None:
        raise AppError(404, "not_found")
    return [sent["en"]]


def record_attempt(conn: sqlite3.Connection, clock: Clock, user_id: str,
                   data: AttemptIn) -> tuple[AttemptOut, bool]:
    """Return (result, created). A replayed client_attempt_id returns the original (created=False)."""
    is_reflex = data.mode == "reflex"
    if is_reflex and (data.reflex_level is None or (data.reflex_ms is None and not data.skipped)):
        raise AppError(422, "validation_error", fields={"reflex_ms": "reflex_level and reflex_ms are required"})
    limit = scoring.LEVEL_LIMITS_MS[data.reflex_level] if data.reflex_level else 0
    if is_reflex and data.reflex_ms is not None and not scoring.reflex_ms_valid(data.reflex_ms, limit):
        raise AppError(422, "validation_error", fields={"reflex_ms": "out of range"})
    now = clock.now()
    now_iso = iso(now)
    with transaction(conn):
        prior = repo.get_attempt(conn, user_id, data.client_attempt_id)
        if prior:
            return _out(prior, repo.unlocked_levels(conn, user_id, prior["card_id"])), False
        card = repo.card_for_view(conn, data.card_id)
        if card is None or not policy.can_view(user_id, card["owner_id"], card["owner_kind"] == "system",
                                               card["visibility"], card["moderation_status"]):
            raise AppError(404, "not_found")
        targets = _targets(conn, card, data)
        if data.reflex_session_id:
            sess = repo.get_session(conn, data.reflex_session_id)
            if sess is None or sess["user_id"] != user_id:
                raise AppError(404, "not_found")
        level = ITEM_LEVEL[data.item_type]
        practice = not is_reflex
        if practice and level > 1:
            prog = repo.get_progress(conn, user_id, data.card_id, level)
            if not prog or not prog["unlocked"]:
                raise AppError(409, "level_locked")
        timeout = is_reflex and not data.skipped and scoring.is_timeout(data.reflex_ms, limit)
        if data.skipped or timeout:
            acc, transcript = 0, (None if data.skipped else data.transcript)
        else:
            acc, transcript = scoring.accuracy(data.item_type, data.transcript, targets), data.transcript
        reflex_score = None
        if is_reflex:
            if data.skipped or timeout:
                reflex_score = 0
            else:
                reflex_score = scoring.round_half_up(scoring.reflex_score(acc, data.reflex_ms, limit))
        score = reflex_score if reflex_score is not None else acc
        q = srs.quality_from_score(score)
        row = {"id": str(uuid.uuid4()), "client_attempt_id": data.client_attempt_id, "user_id": user_id,
               "card_id": data.card_id, "item_type": data.item_type, "item_id": data.item_id, "mode": data.mode,
               "reflex_level": data.reflex_level if is_reflex else None,
               "reflex_session_id": data.reflex_session_id, "transcript": transcript, "accuracy": acc,
               "pronunciation": None if data.pronunciation is None else max(0, min(100, data.pronunciation)),
               "reflex_ms": data.reflex_ms if is_reflex else None, "reflex_score": reflex_score,
               "xp": stats.xp_for_score(score), "created_at": now_iso}
        repo.insert_attempt(conn, row)
        old = repo.get_review(conn, user_id, data.item_type, data.item_id)
        state = srs.SrsState(old["ease"], old["reps"], old["interval_days"], old["lapses"]) if old else srs.SrsState()
        new = srs.next_state(state, q)
        repo.upsert_review(conn, user_id, data.item_type, data.item_id, data.card_id, new.ease, new.interval,
                           new.reps, new.lapses, iso(srs.due_at(now, new.interval)), now_iso)
        if practice:
            ids = repo.level_item_ids(conn, card["content_id"], data.item_type)
            latest = repo.practice_scores(conn, user_id, data.card_id, data.item_type)
            lscore = stats.level_score([latest.get(i) for i in ids])
            repo.upsert_progress(conn, user_id, data.card_id, level, round(lscore), 1 if level == 1 else 0, now_iso)
            if level < stats.PRACTICE_LEVELS and stats.meets_practice_unlock(lscore):
                repo.upsert_progress(conn, user_id, data.card_id, level + 1, 0, 1, now_iso)
        out = _out(row, repo.unlocked_levels(conn, user_id, data.card_id))
    return out, True


# --- reflex ----------------------------------------------------------------------------------

def start_reflex(conn: sqlite3.Connection, clock: Clock, user: dict, level: int) -> dict:
    if level > user["reflex_level_unlocked"]:
        raise AppError(409, "level_locked")
    now = clock.now()
    with transaction(conn):
        rounds = repo.due_label_items(conn, user["id"], iso(now), REFLEX_ROUNDS)
        if len(rounds) < REFLEX_ROUNDS:
            seen = {r["item_id"] for r in rounds}
            extra = [r for r in repo.new_label_items(conn, user["id"], REFLEX_ROUNDS) if r["item_id"] not in seen]
            rounds += extra[:REFLEX_ROUNDS - len(rounds)]
        for r in rounds:
            r["item_type"] = "label"
        sid = str(uuid.uuid4())
        repo.insert_session(conn, sid, user["id"], level, rounds, iso(now))
    return {"session_id": sid, "level": level, "limit_ms": scoring.LEVEL_LIMITS_MS[level], "rounds": rounds}


def complete_reflex(conn: sqlite3.Connection, clock: Clock, user: dict, session_id: str) -> dict:
    with transaction(conn):
        sess = repo.get_session(conn, session_id)
        if sess is None or sess["user_id"] != user["id"]:
            raise AppError(404, "not_found")
        answered, mean = repo.session_summary(conn, session_id)
        current = users_repo.get(conn, user["id"])["reflex_level_unlocked"]
        if sess["completed_at"] is None:
            repo.complete_session(conn, session_id, scoring.round_half_up(mean), iso(clock.now()))
            current = stats.reflex_next_unlocked(current, sess["level"], answered, mean)
            users_repo.set_reflex_level_unlocked(conn, user["id"], current)
            sess = repo.get_session(conn, session_id)
    return {"session_id": session_id, "level": sess["level"], "score": sess["score"], "answered": answered,
            "completed_at": sess["completed_at"], "counted": answered >= stats.REFLEX_MIN_ANSWERED,
            "reflex_level_unlocked": current}


# --- profile ---------------------------------------------------------------------------------

def profile_stats(conn: sqlite3.Connection, clock: Clock, user_id: str) -> dict:
    xp = repo.user_xp(conn, user_id)
    level, progress = stats.level_from_xp(xp)
    streak = stats.streak_days([parse_iso(t) for t in repo.attempt_times(conn, user_id)], clock.now())
    return {"streak": streak, "xp": xp, "level": level, "level_progress": round(progress, 4)}


def mastery_summary(conn: sqlite3.Connection, user_id: str) -> dict:
    out = {"needs_review": 0, "learning": 0, "mastered": 0}
    for scores in repo.card_scores(conn, user_id).values():
        mean = stats.mastery_mean(scores)
        key = ("needs_review" if mean < stats.MASTERY_LEARNING else
               "learning" if mean < stats.MASTERY_MASTERED else "mastered")
        out[key] += 1
    return out
