"""Strict request/response models for attempts and reflex sessions."""
import re
from typing import Literal

from pydantic import BaseModel, Field, StrictBool, StrictInt, field_validator

from .common import StrictModel

_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


class AttemptIn(StrictModel):
    client_attempt_id: str
    card_id: str = Field(min_length=1, max_length=64)
    item_type: Literal["label", "sentence", "story"]
    item_id: str = Field(min_length=1, max_length=64)
    mode: Literal["shadow", "reflex", "auto"]
    transcript: str | None = Field(default=None, max_length=500)
    skipped: StrictBool = False
    pronunciation: StrictInt | None = None
    reflex_level: StrictInt | None = Field(default=None, ge=1, le=4)
    reflex_ms: StrictInt | None = None
    reflex_session_id: str | None = Field(default=None, max_length=64)

    @field_validator("client_attempt_id")
    @classmethod
    def _uuid(cls, v: str) -> str:
        if not _UUID.match(v):
            raise ValueError("must be a UUID")
        return v.lower()


class AttemptOut(BaseModel):
    id: str
    client_attempt_id: str
    accuracy: int
    score: int
    q: int
    xp: int
    timeout: bool
    unlocked_levels: list[int]


class ReflexStartIn(StrictModel):
    level: StrictInt = Field(ge=1, le=4)


class ReflexRound(BaseModel):
    card_id: str
    item_type: str = "label"
    item_id: str
    word: str
    ipa: str | None = None
    audio_file: str | None = None


class ReflexStartOut(BaseModel):
    session_id: str
    level: int
    limit_ms: int
    rounds: list[ReflexRound]


class ReflexCompleteOut(BaseModel):
    session_id: str
    level: int
    score: int
    answered: int
    completed_at: str
    counted: bool
    reflex_level_unlocked: int
