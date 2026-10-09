"""Tokens, scrypt passwords, session arithmetic and the CSRF/Origin rules. Pure: no I/O, no wall clock."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

SESSION_IDLE_DAYS = 90
SESSION_ABSOLUTE_DAYS = 365
DEVICE_COOKIE_DAYS = 400
SCRYPT_R, SCRYPT_P, SCRYPT_DKLEN, SALT_BYTES = 8, 1, 32, 16
CSRF_RE = re.compile(r"[A-Za-z0-9_\-]{32,128}")
_DUMMY_SALT = bytes(SALT_BYTES)


def new_token() -> str:
    """256 random bits, URL-safe (43 characters)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """The only form in which a token is ever stored."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_key(bucket: str, value: str) -> str:
    """Hashed rate-limit key so raw nicknames and IPs are not stored."""
    return hashlib.sha256(f"{bucket}:{value}".encode("utf-8")).hexdigest()


def parse_iso(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)


# --- passwords -------------------------------------------------------------------------------

def _scrypt(password: str, salt: bytes, n: int, r: int, p: int, dklen: int) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=dklen,
                          maxmem=256 * n * r)


def hash_password(password: str, n: int) -> tuple[str, str]:
    """Return (``salt_hex$hash_hex``, params_json) with a fresh per-user salt."""
    salt = secrets.token_bytes(SALT_BYTES)
    digest = _scrypt(password, salt, n, SCRYPT_R, SCRYPT_P, SCRYPT_DKLEN)
    params = json.dumps({"n": n, "r": SCRYPT_R, "p": SCRYPT_P, "dklen": SCRYPT_DKLEN})
    return f"{salt.hex()}${digest.hex()}", params


def verify_password(password: str, stored: str, params_json: str) -> bool:
    try:
        salt_hex, hash_hex = stored.split("$", 1)
        p = json.loads(params_json)
        digest = _scrypt(password, bytes.fromhex(salt_hex), int(p["n"]), int(p["r"]), int(p["p"]),
                         int(p["dklen"]))
        return hmac.compare_digest(digest, bytes.fromhex(hash_hex))
    except (ValueError, KeyError, TypeError):
        return False


def dummy_verify(password: str, n: int) -> bool:
    """Same scrypt cost as a real check, used for unknown nicknames. Always False."""
    digest = _scrypt(password, _DUMMY_SALT, n, SCRYPT_R, SCRYPT_P, SCRYPT_DKLEN)
    return hmac.compare_digest(digest, bytes(SCRYPT_DKLEN)) and False


# --- sessions (DT-13) ------------------------------------------------------------------------

def session_expiry(now: datetime) -> tuple[datetime, datetime]:
    """(sliding idle expiry, absolute expiry) for a session created at ``now``."""
    return now + timedelta(days=SESSION_IDLE_DAYS), now + timedelta(days=SESSION_ABSOLUTE_DAYS)


def slide_expiry(now: datetime, absolute_expires_at: datetime) -> datetime:
    return min(now + timedelta(days=SESSION_IDLE_DAYS), absolute_expires_at)


def session_expired(now: datetime, expires_at: datetime, absolute_expires_at: datetime) -> bool:
    """Expired when ``now >= threshold`` (Addendum 2 #4)."""
    return now >= expires_at or now >= absolute_expires_at


# --- CSRF ------------------------------------------------------------------------------------

def origin_of(url: str) -> str | None:
    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}"


def origin_ok(origin: str | None, referer: str | None, app_origin: str, allow_missing: bool) -> bool:
    """Origin must equal APP_ORIGIN when present; Referer is the fallback; both missing is refused."""
    expected = app_origin.rstrip("/")
    if origin is not None:
        return origin == expected
    if referer is not None:
        return origin_of(referer) == expected
    return allow_missing


def csrf_equal(cookie_value: str | None, header_value: str | None) -> bool:
    if not cookie_value or not header_value:
        return False
    return hmac.compare_digest(cookie_value.encode("utf-8"), header_value.encode("utf-8"))
