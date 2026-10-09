"""Strict request models for profile, settings and account deletion."""
from typing import Literal

from pydantic import Field, StrictBool, model_validator

from .common import StrictModel


class MePatchIn(StrictModel):
    avatar_key: str | None = Field(default=None, min_length=1, max_length=20)
    cefr_level: Literal["A1", "A2", "B1"] | None = None

    @model_validator(mode="after")
    def _one(self) -> "MePatchIn":
        if self.avatar_key is None and self.cefr_level is None:
            raise ValueError("nothing to update")
        return self


class SettingsIn(StrictModel):
    hide_timer: StrictBool


class DeleteMeIn(StrictModel):
    password: str = Field(min_length=1, max_length=256)
