"""Gemini provider (httpx). Not exercised by tests; never logs the API key."""
from __future__ import annotations

import base64
import json

import httpx
from pydantic import ValidationError

from .provider import AIProviderError
from .schema import AnalysisResult

_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_PROMPT = (
    "You are an English coach for Vietnamese school students (ages 11-18), level CEFR A1-B1. "
    "Analyze ONE everyday photo. Return JSON only with keys: topic, topic_tags, cefr_level, "
    "labels[{name, ipa, vi, accepted_answers, cefr, box_2d [ymin,xmin,ymax,xmax] 0-1000, confidence}] "
    "(3-5 concrete visible nouns, no duplicates), descriptions[{en,vi}] (2 short sentences), "
    "story{en,vi}, safety{has_identifiable_faces, has_personal_info, has_nsfw_or_violence, "
    "is_suitable_for_students, reasons}. Vocabulary A1-B1, sentences <= 12 words. Never name "
    "people by identity. If unsuitable for students set is_suitable_for_students=false."
)


def box_to_center(box: list[float]) -> tuple[float, float]:
    """Gemini box_2d [ymin, xmin, ymax, xmax] on 0-1000 -> (x, y) centre in 0..1."""
    if len(box) != 4 or any(not 0 <= v <= 1000 for v in box):
        raise ValueError("invalid box_2d")
    ymin, xmin, ymax, xmax = box
    return round((xmin + xmax) / 2000, 4), round((ymin + ymax) / 2000, 4)


class GeminiProvider:
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash", timeout: float = 30.0) -> None:
        self._api_key = api_key
        self.model = model
        self.timeout = timeout

    def __repr__(self) -> str:
        return f"GeminiProvider(model={self.model!r})"

    def analyze(self, image_bytes: bytes) -> AnalysisResult:
        body = {
            "contents": [{"parts": [
                {"text": _PROMPT},
                {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(image_bytes).decode()}},
            ]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
        }
        try:
            resp = httpx.post(
                _URL.format(model=self.model), json=body,
                headers={"x-goog-api-key": self._api_key}, timeout=self.timeout,
            )
            resp.raise_for_status()
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            return self._parse(json.loads(text))
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, ValidationError) as exc:
            # Do not chain: httpx errors can embed request details.
            raise AIProviderError(f"gemini analysis failed: {type(exc).__name__}") from None

    @staticmethod
    def _parse(raw: dict) -> AnalysisResult:
        for label in raw.get("labels", []):
            label["x"], label["y"] = box_to_center(label.pop("box_2d"))
        return AnalysisResult.model_validate(raw)
