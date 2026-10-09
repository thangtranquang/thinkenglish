"""Upload response models."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .cards import LabelDetail, SentenceOut


class UploadOut(BaseModel):
    content_id: str
    status: Literal["processing", "ready", "failed"]
    dedupe: Literal["none", "in_flight", "ready"]
    ai_calls: int
    card_id: str | None = None


class UploadStatusOut(BaseModel):
    content_id: str
    status: Literal["processing", "ready", "failed"]
    ai_calls: int
    retryable: bool
    card_id: str | None = None
    topic: str | None = None
    cefr_level: str | None = None
    image_url: str | None = None
    labels: list[LabelDetail] = []
    sentences: list[SentenceOut] = []
