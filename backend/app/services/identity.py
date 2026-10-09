"""Who is calling: resolve cookies to a user, track usage sessions, derive the second-visit gate."""
from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime

from ..clock import Clock, iso
from ..config import Settings
from ..db import transaction
from ..repositories import sessions, usage, users
from ..security import hash_token, new_token, parse_iso, session_expired, slide_expiry
from . import policy

TOUCH_SECONDS = 60


@dataclass
class Resolved:
    user: dict
    via: str                       # "session" or "device"
    session: dict | None = None    # session row when via == "session"


def resolve(conn: sqlite3.Connection, now: datetime, session_token: str | None,
            device_token: str | None) -> Resolved | None:
    """Valid login session first, then guest device token. Anything else is "nobody"."""
    if session_token:
        row = sessions.get_session(conn, hash_token(session_token))
        if (row and row["revoked_at"] is None
                and not session_expired(now, parse_iso(row["expires_at"]), parse_iso(row["absolute_expires_at"]))):
            user = users.get(conn, row["user_id"])
            if user and user["kind"] == "registered":
                return Resolved(user, "session", row)
    if device_token:
        dev = sessions.get_device(conn, hash_token(device_token))
        if dev:
            user = users.get(conn, dev["user_id"])
            if user and user["kind"] == "guest":
                return Resolved(user, "device")
    return None


def create_guest(conn: sqlite3.Connection, clock: Clock) -> tuple[dict, str, str]:
    """New guest + device token + first usage session in one transaction. Returns (user, token, usage_id)."""
    now_iso = iso(clock.now())
    user_id, usage_id, token = str(uuid.uuid4()), str(uuid.uuid4()), new_token()
    with transaction(conn):
        users.insert_guest(conn, user_id, now_iso)
        sessions.add_device(conn, hash_token(token), user_id, now_iso)
        usage.insert(conn, usage_id, user_id, now_iso)
    return users.get(conn, user_id), token, usage_id


def touch_usage(conn: sqlite3.Connection, clock: Clock, settings: Settings, resolved: Resolved) -> tuple[dict, str]:
    """Record activity (at most once per 60 s, or per idle window if shorter), start a usage session after idle, evaluate the gate.

    Returns the fresh user row and the current usage session id.
    """
    now = clock.now()
    user = resolved.user
    latest = usage.latest(conn, user["id"])
    if latest is not None:
        idle = (now - parse_iso(latest["last_activity_at"])).total_seconds()
        if idle < min(TOUCH_SECONDS, settings.session_idle_seconds) and not (resolved.session and _session_stale(resolved.session, now)):
            return user, latest["id"]
    now_iso = iso(now)
    with transaction(conn):
        latest = usage.latest(conn, user["id"])
        new_session = latest is None or policy.is_new_session(
            parse_iso(latest["last_activity_at"]), now, settings.session_idle_seconds)
        if new_session:
            usage_id = str(uuid.uuid4())
            prior = usage.count_write_sessions(conn, user["id"])
            flag = policy.gate_state(user["kind"], prior, settings.guest_free_sessions, True,
                                     user["gate_required_at"] is not None)
            usage.insert(conn, usage_id, user["id"], now_iso)
            if flag and user["gate_required_at"] is None:
                users.set_gate(conn, user["id"], now_iso)
            elif not flag and user["gate_required_at"] is not None:
                users.set_gate(conn, user["id"], None)
        else:
            usage_id = latest["id"]
            usage.set_activity(conn, usage_id, now_iso)
        users.set_last_seen(conn, user["id"], now_iso)
        if resolved.session:
            absolute = parse_iso(resolved.session["absolute_expires_at"])
            sessions.slide_session(conn, resolved.session["token_hash"], now_iso, iso(slide_expiry(now, absolute)))
    return users.get(conn, user["id"]), usage_id


def _session_stale(session: dict, now: datetime) -> bool:
    return (now - parse_iso(session["last_seen_at"])).total_seconds() >= TOUCH_SECONDS


def gate_of(user: dict) -> dict | None:
    """Gate descriptor for the client; only guests can be gated."""
    if user["kind"] == "guest" and user["gate_required_at"] is not None:
        return {"reason": "second_visit", "mandatory": True}
    return None


def mark_write(conn: sqlite3.Connection, usage_id: str | None) -> None:
    """Flag the current usage session as having a write (counts toward the second-visit gate)."""
    if usage_id:
        usage.set_had_write(conn, usage_id)
