"""Strict request models for register and login."""
from typing import Literal

from pydantic import Field, StrictBool, StrictInt

from .common import StrictModel


class RegisterIn(StrictModel):
    nickname: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=256)
    birth_year: StrictInt
    avatar_key: str = Field(default="fox", min_length=1, max_length=20)
    cefr_level: Literal["A1", "A2", "B1"] = "A1"
    guardian_email: str | None = Field(default=None, max_length=320)
    guardian_consent: StrictBool | None = None


class LoginIn(StrictModel):
    nickname: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=256)
    discard_guest: StrictBool = False
