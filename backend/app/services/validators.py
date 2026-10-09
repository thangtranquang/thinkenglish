"""Pure input validators: nickname, password, age/guardian, review overrides (OQ-11, 37)."""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Collection, Mapping, Sequence
from datetime import datetime, timedelta, timezone

NICK_RE = re.compile(r"[A-Za-z0-9_.\-]{3,20}")
PHONE_LIKE = re.compile(r"[0-9.\-_]*[0-9][0-9.\-_]*")
NICK_DENYLIST = frozenset({"admin", "administrator", "system", "root", "moderator", "support", "reflexenglish"})
COMMON_PASSWORDS = frozenset({"12345678", "123456789", "1234567890", "password", "password1", "qwertyuiop", "11111111"})
PASSWORD_MIN, PASSWORD_MAX = 8, 128
MIN_AGE, MAX_AGE, GUARDIAN_UNDER = 10, 100, 16
EMAIL_MAX = 254
EMAIL_RE = re.compile(r"[^@\s]+@[^@\s.]+(\.[^@\s.]+)+")
TITLE_MAX, WORD_MIN, WORD_MAX, LABELS_MIN, LABELS_MAX = 60, 1, 40, 1, 8
ICT = timezone(timedelta(hours=7))
TOO_YOUNG_MSG = "ReflexEnglish dành cho học sinh từ 10 tuổi"


class ValidationFailure(ValueError):
    """Rule violation; ``code`` is a stable machine-readable reason."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def validate_nickname(raw: str) -> str:
    nick = unicodedata.normalize("NFKC", raw or "").strip()
    if not NICK_RE.fullmatch(nick):
        raise ValidationFailure("nickname_invalid", "Nickname must be 3-20 characters: A-Z a-z 0-9 _ . -")
    if PHONE_LIKE.fullmatch(nick) and sum(c.isdigit() for c in nick) >= 7:
        raise ValidationFailure("nickname_invalid", "Nickname must not look like a phone number")
    if nick.lower() in NICK_DENYLIST:
        raise ValidationFailure("nickname_reserved", "Nickname is not allowed")
    return nick


def validate_password(password: str, nickname: str) -> str:
    if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        raise ValidationFailure("password_length", "Password must be 8-128 characters")
    if password.lower() == nickname.lower() or password.lower() in COMMON_PASSWORDS:
        raise ValidationFailure("password_weak", "Password is too easy to guess")
    return password


def current_year_ict(now: datetime) -> int:
    return now.astimezone(ICT).year


def validate_birth_year(value: object, current_year: int) -> int:
    """Return the age; reject non-integers, future years, age < 10 or > 100."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationFailure("birth_year_invalid", "Birth year must be an integer")
    age = current_year - value
    if age < 0:
        raise ValidationFailure("birth_year_invalid", "Birth year is in the future")
    if age < MIN_AGE:
        raise ValidationFailure("too_young", TOO_YOUNG_MSG)
    if age > MAX_AGE:
        raise ValidationFailure("birth_year_invalid", "Birth year is out of range")
    return age


def guardian_required(age: int) -> bool:
    return age < GUARDIAN_UNDER


def validate_guardian(age: int, email: str | None, consent: bool | None) -> None:
    if not guardian_required(age):
        if email is not None or consent:
            raise ValidationFailure("guardian_not_allowed", "Guardian fields are only for under 16")
        return
    if not email:
        raise ValidationFailure("guardian_email", "Guardian email is required")
    if len(email) > EMAIL_MAX or not EMAIL_RE.fullmatch(email):
        raise ValidationFailure("guardian_email", "Guardian email is invalid")
    if consent is not True:
        raise ValidationFailure("guardian_consent", "Guardian consent is required")


def validate_review_overrides(content_label_ids: Collection[str], title: str | None,
                              labels: Sequence[Mapping[str, object]]) -> None:
    """Title <= 60; 1-8 labels, each an existing label id, word 1-40, unique case-insensitive, x/y in 0..1."""
    if title is not None and len(title) > TITLE_MAX:
        raise ValidationFailure("title_too_long")
    if not LABELS_MIN <= len(labels) <= LABELS_MAX:
        raise ValidationFailure("label_count")
    seen: set[str] = set()
    for item in labels:
        if item.get("id") not in content_label_ids:
            raise ValidationFailure("label_unknown")
        word = item.get("word")
        if not isinstance(word, str) or not WORD_MIN <= len(word) <= WORD_MAX:
            raise ValidationFailure("label_word")
        key = word.strip().lower()
        if key in seen:
            raise ValidationFailure("label_duplicate")
        seen.add(key)
        for axis in ("x", "y"):
            pos = item.get(axis)
            if not isinstance(pos, (int, float)) or isinstance(pos, bool) or not 0 <= pos <= 1:
                raise ValidationFailure("label_position")
