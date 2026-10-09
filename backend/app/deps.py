"""FastAPI dependency chain: csrf -> identity -> touch_usage -> not_gated -> registered(reason).

Use ``current_user`` for "any identity", ``not_gated_user`` for gated endpoints and
``registered_user("camera" | "account" | "profile")`` for registered-only endpoints.
Later slices call ``mark_write(user)`` after a successful write so the usage session counts toward
the second-visit gate.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, Request, Response

from .clock import Clock
from .config import Settings
from .db import connect
from .errors import AppError
from .security import CSRF_RE, DEVICE_COOKIE_DAYS, csrf_equal, new_token, origin_ok
from .services import identity as identity_service

DEVICE_COOKIE = "re_device"
SESSION_COOKIE = "re_session"
CSRF_COOKIE = "re_csrf"
CSRF_HEADER = "X-CSRF-Token"
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
SESSION_COOKIE_DAYS = 90

# (method, path) pairs that stay reachable for a gated guest. Static files are not API routes.
# The route-walk test (TC-4.3) treats every other /api route as gated.
GATE_EXEMPT: frozenset[tuple[str, str]] = frozenset({
    ("GET", "/api/health"), ("GET", "/api/config"),
    ("POST", "/api/session/bootstrap"), ("POST", "/api/session/heartbeat"),
    ("POST", "/api/auth/register"), ("POST", "/api/auth/login"), ("POST", "/api/auth/logout"),
    ("GET", "/api/me"),
})


def settings_of(request: Request) -> Settings:
    return request.app.state.settings


def clock_of(request: Request) -> Clock:
    return request.app.state.clock


def client_ip(request: Request) -> str:
    """Socket peer only; forwarded headers are never trusted."""
    return request.client.host if request.client else "unknown"


def get_conn(request: Request) -> Iterator[sqlite3.Connection]:
    conn = connect(settings_of(request).db_path)
    try:
        yield conn
    finally:
        conn.close()


# --- cookies -----------------------------------------------------------------------------------

def csrf_cookie_name(settings: Settings) -> str:
    return CSRF_COOKIE if settings.is_local else f"__Host-{CSRF_COOKIE}"


def set_cookie(response: Response, settings: Settings, name: str, value: str, days: int, *,
               http_only: bool = True) -> None:
    response.set_cookie(name, value, max_age=days * 86400, path="/", httponly=http_only,
                        samesite="lax", secure=not settings.is_local)


def clear_cookie(response: Response, settings: Settings, name: str, *, http_only: bool = True) -> None:
    response.set_cookie(name, "", max_age=0, expires=0, path="/", httponly=http_only,
                        samesite="lax", secure=not settings.is_local)


def ensure_csrf_cookie(request: Request, response: Response) -> str:
    """Keep the browser's CSRF token stable; mint one only when missing or malformed."""
    settings = settings_of(request)
    existing = request.cookies.get(csrf_cookie_name(settings))
    token = existing if existing and CSRF_RE.fullmatch(existing) else new_token()
    set_cookie(response, settings, csrf_cookie_name(settings), token, DEVICE_COOKIE_DAYS, http_only=False)
    return token


# --- the chain ---------------------------------------------------------------------------------

def origin_guard(request: Request) -> None:
    """Origin (or Referer) must match APP_ORIGIN when present. Used alone by bootstrap."""
    s = settings_of(request)
    if not origin_ok(request.headers.get("origin"), request.headers.get("referer"), s.app_origin,
                     allow_missing=True):
        raise AppError(403, "csrf_failed")


def csrf(request: Request) -> None:
    """State-changing requests: Origin/Referer required and matching, plus double-submit token."""
    if request.method not in UNSAFE_METHODS:
        return
    s = settings_of(request)
    if not origin_ok(request.headers.get("origin"), request.headers.get("referer"), s.app_origin,
                     allow_missing=False):
        raise AppError(403, "csrf_failed")
    if not csrf_equal(request.cookies.get(csrf_cookie_name(s)), request.headers.get(CSRF_HEADER)):
        raise AppError(403, "csrf_failed")


@dataclass
class CurrentUser:
    """The caller. ``row`` is the users row as a dict (never serialize it directly)."""
    conn: sqlite3.Connection
    row: dict
    via: str
    session_token: str | None
    usage_id: str | None = None
    resolved: identity_service.Resolved | None = None

    @property
    def id(self) -> str:
        return self.row["id"]

    @property
    def kind(self) -> str:
        return self.row["kind"]

    @property
    def is_guest(self) -> bool:
        return self.row["kind"] == "guest"

    @property
    def gate(self) -> dict | None:
        return identity_service.gate_of(self.row)


def mark_write(user: CurrentUser) -> None:
    """Flag the caller's current usage session as having a write. Call after each successful write."""
    identity_service.mark_write(user.conn, user.usage_id)


def optional_identity(request: Request, conn: sqlite3.Connection = Depends(get_conn)) -> CurrentUser | None:
    """Resolve cookies without recording activity. None when nobody is recognised."""
    found = identity_service.resolve(conn, clock_of(request).now(), request.cookies.get(SESSION_COOKIE),
                                     request.cookies.get(DEVICE_COOKIE))
    if found is None:
        return None
    token = request.cookies.get(SESSION_COOKIE) if found.session else None
    return CurrentUser(conn, found.user, found.via, token, resolved=found)


def identity(user: CurrentUser | None = Depends(optional_identity)) -> CurrentUser:
    if user is None:
        raise AppError(401, "no_session")
    return user


def current_user(request: Request, _csrf: None = Depends(csrf),
                 user: CurrentUser = Depends(identity)) -> CurrentUser:
    """csrf -> identity -> touch_usage. Starts/extends the usage session and refreshes the gate."""
    row, usage_id = identity_service.touch_usage(user.conn, clock_of(request), settings_of(request),
                                                 user.resolved)
    user.row, user.usage_id = row, usage_id
    return user


def not_gated_user(user: CurrentUser = Depends(current_user)) -> CurrentUser:
    if user.gate is not None:
        raise AppError(403, "registration_required", reason=user.gate["reason"])
    return user


def registered_user(reason: str) -> Callable[..., Any]:
    """Dependency factory: 403 ``registration_required`` (reason camera/account/profile) for guests."""
    def dependency(user: CurrentUser = Depends(not_gated_user)) -> CurrentUser:
        if user.kind != "registered":
            raise AppError(403, "registration_required", reason=reason)
        return user
    return dependency
