"""Validated AI analysis result (spec v1.1 section 6, coordinates already normalised)."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Label(_Strict):
    name: str = Field(min_length=1, max_length=80)
    ipa: str = Field(default="", max_length=120)
    vi: str = Field(min_length=1, max_length=120)
    accepted_answers: list[str] = Field(default_factory=list, max_length=10)
    cefr: str = Field(default="A1", pattern=r"^(A1|A2|B1|B2)$")
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class Description(_Strict):
    en: str = Field(min_length=1, max_length=300)
    vi: str = Field(default="", max_length=300)


class Story(_Strict):
    en: str = Field(min_length=1, max_length=800)
    vi: str = Field(default="", max_length=800)


class Safety(_Strict):
    has_identifiable_faces: bool = False
    has_personal_info: bool = False
    has_nsfw_or_violence: bool = False
    is_suitable_for_students: bool = True
    reasons: list[str] = Field(default_factory=list, max_length=10)


class AnalysisResult(_Strict):
    topic: str = Field(min_length=1, max_length=80)
    topic_tags: list[str] = Field(default_factory=list, max_length=10)
    cefr_level: str = Field(pattern=r"^(A1|A2|B1|B2)$")
    labels: list[Label] = Field(min_length=3, max_length=8)
    descriptions: list[Description] = Field(min_length=1, max_length=4)
    story: Story
    safety: Safety

    @model_validator(mode="after")
    def _unique_labels(self) -> "AnalysisResult":
        names = [l.name.strip().lower() for l in self.labels]
        if len(set(names)) != len(names):
            raise ValueError("duplicate label names")
        return self
