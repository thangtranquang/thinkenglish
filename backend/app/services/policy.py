"""Pure policy rules: idle/usage gate, sliding rate window, card visibility, share decision.

Boundary rule (Addendum 2 #4): a threshold is reached when ``age >= window``; the one
exception is the idle rule, where a new session needs ``idle > limit`` strictly.
"""
from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime


def is_new_session(last_activity: datetime, now: datetime, idle_seconds: float) -> bool:
    return (now - last_activity).total_seconds() > idle_seconds


def prior_write_sessions(had_write_flags: Sequence[bool]) -> int:
    """Count write sessions before the current one (the last flag, chronologically)."""
    return sum(1 for flag in list(had_write_flags)[:-1] if flag)


def gate_required(prior_write_sessions_: int, free_sessions: int) -> bool:
    return prior_write_sessions_ >= free_sessions


def gate_state(kind: str, prior: int, free_sessions: int, new_session: bool, gate_flag: bool) -> bool:
    """New gate flag: only guests are gated; evaluated on a new session, otherwise unchanged."""
    if kind != "guest":
        return False
    return gate_required(prior, free_sessions) if new_session else gate_flag


def count_in_window(events: Sequence[float], now: float, window: float) -> int:
    """Events strictly younger than the window; age >= window is outside."""
    return sum(1 for t in events if now - t < window)


def window_exceeded(events: Sequence[float], now: float, limit: int, window: float) -> bool:
    return count_in_window(events, now, window) >= limit


def retry_after(events: Sequence[float], now: float, limit: int, window: float) -> int:
    """Whole seconds (>= 1) until enough events leave the window to allow another."""
    inside = sorted(t for t in events if now - t < window)
    excess = len(inside) - limit + 1
    if excess <= 0:
        return 0
    return max(1, math.ceil(inside[excess - 1] + window - now))


def can_view(viewer_id: str | None, owner_id: str | None, is_system: bool,
             visibility: str, moderation_status: str) -> bool:
    if is_system or (viewer_id is not None and viewer_id == owner_id):
        return True
    return visibility == "public" and moderation_status == "approved"


@dataclass(frozen=True)
class ShareDecision:
    allowed: bool
    reason: str | None
    moderation_status: str


def share_decision(faces: bool, personal_info: bool, nsfw_or_violence: bool, suitable: bool) -> ShareDecision:
    """Reason priority: faces > personal_info > unsuitable."""
    if faces:
        reason = "faces"
    elif personal_info:
        reason = "personal_info"
    elif nsfw_or_violence or not suitable:
        reason = "unsuitable"
    else:
        return ShareDecision(True, None, "approved")
    return ShareDecision(False, reason, "rejected")


_CONTACT_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|(?<!\w)@\w{2,}|https?:|www\.|\b[\w-]+\.(?:com|net|org|vn|io|me|co)\b", re.I)


def unsafe_text(*texts: str | None) -> bool:
    """True when free text holds contact info or links: phone-like digit runs, emails, URLs, @handles."""
    for text in texts:
        if not text:
            continue
        if _CONTACT_RE.search(text):
            return True
        for run in re.findall(r"\+?\d[\d\s.()-]*\d", text):
            if sum(c.isdigit() for c in run) >= 8:
                return True
    return False
