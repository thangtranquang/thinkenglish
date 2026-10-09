"""Register (guest converted in place), login, logout and the sliding-window rate limits."""
from __future__ import annotations

import sqlite3
import unicodedata
from datetime import timedelta

from ..clock import Clock, iso
from ..config import Settings
from ..db import transaction
from ..errors import AppError
from ..repositories import sessions, usage, users
from ..schemas.auth import LoginIn, RegisterIn
from ..security import (dummy_verify, hash_key, hash_password, hash_token, new_token, parse_iso,
                        session_expiry, verify_password)
from . import policy, validators

_FIELD_OF = {
    "nickname_invalid": "nickname", "nickname_reserved": "nickname",
    "password_length": "password", "password_weak": "password",
    "birth_year_invalid": "birth_year", "too_young": "birth_year",
    "guardian_email": "guardian_email", "guardian_consent": "guardian_consent",
    "guardian_not_allowed": "guardian_email",
}


def invalid_credentials() -> AppError:
    """One generic error for unknown nickname and wrong password (identical bytes)."""
    return AppError(401, "invalid_credentials")


# --- rate limits -----------------------------------------------------------------------------

def _limit_and_window(settings: Settings, bucket: str) -> tuple[int, int]:
    if bucket == "login_nick":
        return settings.login_fail_per_nickname, settings.login_window_seconds
    if bucket == "login_ip":
        return settings.login_fail_per_ip, settings.login_window_seconds
    return settings.register_per_ip, settings.register_window_seconds


def _events(conn: sqlite3.Connection, clock: Clock, settings: Settings, bucket: str, key: str) -> list[float]:
    _, window = _limit_and_window(settings, bucket)
    since = iso(clock.now() - timedelta(seconds=window))
    rows = usage.rate_events_since(conn, bucket, hash_key(bucket, key), since)
    return [parse_iso(t).timestamp() for t in rows]


def check_limit(conn: sqlite3.Connection, clock: Clock, settings: Settings, bucket: str, key: str) -> None:
    """Raise 429 + Retry-After when the sliding window for this key is full."""
    limit, window = _limit_and_window(settings, bucket)
    events, now = _events(conn, clock, settings, bucket, key), clock.now().timestamp()
    if policy.window_exceeded(events, now, limit, window):
        wait = policy.retry_after(events, now, limit, window)
        raise AppError(429, "rate_limited", headers={"Retry-After": str(wait)},
                       fields={"message": f"Bạn thử quá nhiều lần. Vui lòng đợi {wait} giây rồi thử lại."})


def record_event(conn: sqlite3.Connection, clock: Clock, bucket: str, key: str) -> None:
    usage.add_rate_event(conn, bucket, hash_key(bucket, key), iso(clock.now()))


def normalize_nickname(raw: str) -> str:
    return unicodedata.normalize("NFKC", raw or "").strip().lower()


def check_login_limits(conn: sqlite3.Connection, clock: Clock, settings: Settings, nickname: str, ip: str) -> None:
    """Both failure buckets (per nickname, per IP) must have room. Shared with account deletion."""
    blocked: list[AppError] = []
    for bucket, key in (("login_nick", normalize_nickname(nickname)), ("login_ip", ip)):
        try:
            check_limit(conn, clock, settings, bucket, key)
        except AppError as exc:
            blocked.append(exc)
    if blocked:
        raise max(blocked, key=lambda e: int(e.headers["Retry-After"]))


def record_login_failure(conn: sqlite3.Connection, clock: Clock, nickname: str, ip: str) -> None:
    record_event(conn, clock, "login_nick", normalize_nickname(nickname))
    record_event(conn, clock, "login_ip", ip)


# --- register --------------------------------------------------------------------------------

def _validate_registration(data: RegisterIn, current_year: int, avatars: list[str]) -> tuple[str, int]:
    """Return (nickname, age); raise 422 naming the failing field."""
    try:
        nickname = validators.validate_nickname(data.nickname)
        validators.validate_password(data.password, nickname)
        age = validators.validate_birth_year(data.birth_year, current_year)
        validators.validate_guardian(age, data.guardian_email, data.guardian_consent)
    except validators.ValidationFailure as exc:
        raise AppError(422, exc.code, fields={_FIELD_OF.get(exc.code, "body"): str(exc)}) from exc
    if data.avatar_key not in avatars:
        raise AppError(422, "validation_error", fields={"avatar_key": "unknown avatar"})
    return nickname, age


def register(conn: sqlite3.Connection, clock: Clock, settings: Settings, guest: dict, data: RegisterIn,
             avatars: list[str]) -> str:
    """Convert ``guest`` into a registered user in place. Returns the new session token."""
    if guest["kind"] != "guest":
        raise AppError(409, "already_registered")
    now = clock.now()
    nickname, age = _validate_registration(data, validators.current_year_ict(now), avatars)
    under_16 = validators.guardian_required(age)
    pw_hash, pw_params = hash_password(data.password, settings.scrypt_n)  # slow: before taking the write lock
    now_iso = iso(now)
    token = new_token()
    expires, absolute = session_expiry(now)
    try:
        with transaction(conn):
            current = users.get(conn, guest["id"])
            if current is None or current["kind"] != "guest":
                raise AppError(409, "already_registered")
            if users.get_registered_by_nickname_ci(conn, nickname.lower()):
                raise AppError(409, "nickname_taken")
            users.convert_to_registered(
                conn, guest["id"], nickname=nickname, password_hash=pw_hash, password_params=pw_params,
                avatar_key=data.avatar_key, birth_year=data.birth_year, cefr_level=data.cefr_level,
                guardian_email=data.guardian_email if under_16 else None,
                guardian_consent_at=now_iso if under_16 else None, now_iso=now_iso)
            sessions.delete_devices_for_user(conn, guest["id"])
            sessions.add_session(conn, hash_token(token), guest["id"], now_iso, iso(expires), iso(absolute))
    except sqlite3.IntegrityError as exc:  # lost a race on the unique nickname index
        raise AppError(409, "nickname_taken") from exc
    return token


# --- login / logout --------------------------------------------------------------------------

def login(conn: sqlite3.Connection, clock: Clock, settings: Settings, current: dict | None, data: LoginIn,
          ip: str) -> tuple[dict, str]:
    """Verify credentials, retire the browser's current guest, open a session. Returns (user, token)."""
    check_login_limits(conn, clock, settings, data.nickname, ip)
    account = users.get_registered_by_nickname_ci(conn, normalize_nickname(data.nickname))
    if account is None:
        dummy_verify(data.password, settings.scrypt_n)
        ok = False
    else:
        ok = verify_password(data.password, account["password_hash"], account["password_params"])
    if not ok:
        record_login_failure(conn, clock, data.nickname, ip)
        raise invalid_credentials()
    now = clock.now()
    now_iso = iso(now)
    token = new_token()
    expires, absolute = session_expiry(now)
    with transaction(conn):
        if current is not None and current["kind"] == "guest":
            if users.has_progress(conn, current["id"]) and not data.discard_guest:
                raise AppError(409, "guest_has_progress")
            users.delete(conn, current["id"])  # cascades device tokens, usage sessions, progress
        users.set_gate(conn, account["id"], None)
        users.set_last_seen(conn, account["id"], now_iso)
        sessions.add_session(conn, hash_token(token), account["id"], now_iso, iso(expires), iso(absolute))
    return users.get(conn, account["id"]), token


def logout(conn: sqlite3.Connection, clock: Clock, session_token: str | None) -> None:
    """Revoke the presented session if any. Idempotent."""
    if session_token:
        sessions.revoke_session(conn, hash_token(session_token), iso(clock.now()))


def logout_all(conn: sqlite3.Connection, clock: Clock, user_id: str) -> None:
    sessions.revoke_all_for_user(conn, user_id, iso(clock.now()))
