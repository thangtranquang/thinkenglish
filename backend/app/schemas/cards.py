"""Card request/response models."""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from .common import StrictModel


class LabelOverride(StrictModel):
    id: str = Field(min_length=1, max_length=64)
    word: str = Field(min_length=1, max_length=40)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class CardCreateIn(StrictModel):
    content_id: UUID
    title: str | None = Field(default=None, max_length=60)
    label_overrides: list[LabelOverride] | None = Field(default=None, max_length=8)


class LabelBrief(BaseModel):
    word: str
    ipa: str | None
    audio_url: str | None


class CardItem(BaseModel):
    id: str
    title: str
    topic: str | None
    labels: list[LabelBrief]
    mastery: int | None
    image_url: str
    owner_nickname: str | None
    saved: bool
    is_mine: bool


class CardPage(BaseModel):
    items: list[CardItem]
    has_more: bool


class LabelDetail(BaseModel):
    id: str
    word: str
    ipa: str | None
    vi_meaning: str | None
    x: float | None
    y: float | None
    accepted_answers: list[str]
    audio_url: str | None


class SentenceOut(BaseModel):
    id: str
    kind: str
    en: str
    vi: str | None
    audio_url: str | None


class CardDetail(BaseModel):
    id: str
    title: str
    topic: str | None
    cefr_level: str | None
    visibility: str
    owner_nickname: str | None
    is_mine: bool
    saved: bool
    mastery: int | None
    image_url: str
    unlocked_levels: list[int] = [1]
    labels: list[LabelDetail]
    sentences: list[SentenceOut]


class TopicOut(BaseModel):
    name: str
    count: int


class TopicsOut(BaseModel):
    items: list[TopicOut]
