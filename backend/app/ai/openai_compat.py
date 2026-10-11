"""Provider for any OpenAI-compatible chat-completions endpoint with a vision model (llama.cpp, vLLM...).

Never logs or echoes the API key. Thinking is switched off (`enable_thinking: false`): the task is a plain
JSON extraction and a reasoning model would otherwise spend 20-30 s thinking.
"""
from __future__ import annotations

import base64
import json

import httpx
from pydantic import ValidationError

from .provider import AIProviderError
from .schema import AnalysisResult

_PROMPT = (
    "You are an English coach for Vietnamese school students (ages 11-18), level CEFR A1-B1. "
    "Look at ONE everyday photo and answer with a single JSON object and nothing else:\n"
    '{"topic": "short English topic", "topic_tags": ["tag"], "cefr_level": "A1|A2|B1",\n'
    ' "labels": [{"name": "apple", "ipa": "/ˈæp.əl/", "vi": "quả táo", "accepted_answers": ["apples"],\n'
    '             "cefr": "A1", "x": 0.26, "y": 0.58, "confidence": 0.9}],\n'
    ' "descriptions": [{"en": "An apple is on the plate.", "vi": "Một quả táo ở trên đĩa."}],\n'
    ' "story": {"en": "2-3 short sentences.", "vi": "Bản dịch tiếng Việt."},\n'
    ' "safety": {"has_identifiable_faces": false, "has_personal_info": false, '
    '"has_nsfw_or_violence": false, "is_suitable_for_students": true, "reasons": []}}\n'
    "Rules: 3 to 5 concrete, clearly visible objects as labels (no duplicates). x and y are the CENTRE of the "
    "object as fractions of the image width and height (0.0 to 1.0; x counts from the left, y from the top). "
    "Exactly 2 descriptions of at most 12 words. Vocabulary A1-B1 only. Vietnamese in the vi fields. "
    "Never name a real person. If the photo shows identifiable faces, personal information (plates, documents, "
    "screens with text) or anything unsuitable for children, set the matching safety flag to true and "
    "is_suitable_for_students to false."
)
_CEFR = {"A1", "A2", "B1", "B2"}


def _mime(data: bytes) -> str:
    if data[:4] == b"\x89PNG":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def _loads(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in the answer")
    out = json.loads(text[start:end + 1])
    if not isinstance(out, dict):
        raise ValueError("JSON answer is not an object")
    return out


def _clamp(value, default: float = 0.5) -> float:
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return default


def _text(value, limit: int, default: str = "") -> str:
    return (str(value).strip() if value is not None else default)[:limit]


def _sentence(item) -> dict:
    if isinstance(item, str):
        return {"en": _text(item, 300)}
    item = item if isinstance(item, dict) else {}
    return {"en": _text(item.get("en"), 300), "vi": _text(item.get("vi"), 300)}


def _label(lab: dict) -> dict:
    name = _text(lab.get("name"), 80)
    cefr = _text(lab.get("cefr"), 2).upper()
    answers = lab.get("accepted_answers") if isinstance(lab.get("accepted_answers"), list) else []
    return {"name": name, "ipa": _text(lab.get("ipa"), 120), "vi": _text(lab.get("vi"), 120) or name,
            "accepted_answers": [_text(a, 80) for a in answers if _text(a, 80)][:10],
            "cefr": cefr if cefr in _CEFR else "A1", "x": _clamp(lab.get("x")), "y": _clamp(lab.get("y")),
            "confidence": _clamp(lab.get("confidence"), 1.0)}


def _normalise(raw: dict) -> dict:
    """Keep only the fields the schema knows: models like to add extras or return slightly off values."""
    labels, seen = [], set()
    for lab in raw.get("labels") or []:
        if not isinstance(lab, dict):
            continue
        item = _label(lab)
        if item["name"] and item["name"].lower() not in seen:
            seen.add(item["name"].lower())
            labels.append(item)
    cefr = _text(raw.get("cefr_level"), 2).upper()
    safety = raw.get("safety") if isinstance(raw.get("safety"), dict) else {}
    return {
        "topic": _text(raw.get("topic"), 80, "Daily life") or "Daily life",
        "topic_tags": [_text(t, 40) for t in (raw.get("topic_tags") or []) if _text(t, 40)][:10]
        if isinstance(raw.get("topic_tags"), list) else [],
        "cefr_level": cefr if cefr in _CEFR else "A2",
        "labels": labels[:8],
        "descriptions": [_sentence(d) for d in (raw.get("descriptions") or [])[:4]],
        "story": _sentence(raw.get("story")),
        "safety": {
            "has_identifiable_faces": bool(safety.get("has_identifiable_faces", False)),
            "has_personal_info": bool(safety.get("has_personal_info", False)),
            "has_nsfw_or_violence": bool(safety.get("has_nsfw_or_violence", False)),
            "is_suitable_for_students": bool(safety.get("is_suitable_for_students", True)),
            "reasons": [_text(r, 200) for r in (safety.get("reasons") or []) if isinstance(r, str)][:10],
        },
    }


class OpenAICompatProvider:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 120.0,
                 transport: httpx.BaseTransport | None = None) -> None:
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._api_key = api_key
        self.model = model
        self.timeout = timeout
        self._transport = transport

    def __repr__(self) -> str:
        return f"OpenAICompatProvider(url={self._url!r}, model={self.model!r})"

    def analyze(self, image_bytes: bytes) -> AnalysisResult:
        data_url = f"data:{_mime(image_bytes)};base64,{base64.b64encode(image_bytes).decode()}"
        body = {
            "model": self.model,
            "temperature": 0.2,
            "max_tokens": 3000,
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": _PROMPT},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]}],
        }
        try:
            with httpx.Client(timeout=self.timeout, transport=self._transport) as client:
                resp = client.post(self._url, json=body, headers={"Authorization": f"Bearer {self._api_key}"})
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"] or ""
            return AnalysisResult.model_validate(_normalise(_loads(text)))
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, ValidationError) as exc:
            # Do not chain: httpx errors can embed request details.
            raise AIProviderError(f"llm analysis failed: {type(exc).__name__}") from None
