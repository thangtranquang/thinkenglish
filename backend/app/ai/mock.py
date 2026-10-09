"""Deterministic provider used by all tests (derived from image sha256)."""
from __future__ import annotations

import hashlib
import threading
import time
from typing import Callable

from .schema import AnalysisResult

_WORDS = [
    ("apple", "/ˈæp.əl/", "quả táo", "A1"), ("book", "/bʊk/", "quyển sách", "A1"),
    ("chair", "/tʃeər/", "cái ghế", "A1"), ("table", "/ˈteɪ.bəl/", "cái bàn", "A1"),
    ("window", "/ˈwɪn.dəʊ/", "cửa sổ", "A1"), ("bag", "/bæɡ/", "cái túi", "A1"),
    ("bottle", "/ˈbɒt.əl/", "cái chai", "A2"), ("lamp", "/læmp/", "cái đèn", "A2"),
    ("clock", "/klɒk/", "đồng hồ", "A1"), ("pencil", "/ˈpen.səl/", "bút chì", "A1"),
    ("plant", "/plɑːnt/", "cái cây", "A2"), ("shoe", "/ʃuː/", "chiếc giày", "A1"),
]
_TOPICS = ["Home", "School", "Food", "Street", "Garden", "Kitchen"]


class MockProvider:
    """Hooks (delay, block_on, script) are inert unless a test sets them."""

    def __init__(
        self,
        delay: float = 0,
        block_on: threading.Event | None = None,
        script: Callable[[int, bytes], AnalysisResult | None] | None = None,
    ) -> None:
        self.delay = delay
        self.block_on = block_on
        self.script = script
        self.call_count = 0
        self.max_concurrency = 0
        self._active = 0
        self._lock = threading.Lock()

    def analyze(self, image_bytes: bytes) -> AnalysisResult:
        with self._lock:
            self.call_count += 1
            n = self.call_count
            self._active += 1
            self.max_concurrency = max(self.max_concurrency, self._active)
        try:
            if self.block_on is not None:
                self.block_on.wait(timeout=30)
            if self.delay:
                time.sleep(self.delay)
            if self.script is not None:
                scripted = self.script(n, image_bytes)  # may raise to simulate failure
                if scripted is not None:
                    return scripted
            return self._build(hashlib.sha256(image_bytes).digest())
        finally:
            with self._lock:
                self._active -= 1

    @staticmethod
    def _build(d: bytes) -> AnalysisResult:
        start = d[0] % len(_WORDS)
        count = 3 + d[1] % 3
        labels = []
        for i in range(count):
            # stride 5 is coprime with 12 and count <= 5, so names never collide
            name, ipa, vi, cefr = _WORDS[(start + i * 5) % len(_WORDS)]
            labels.append({
                "name": name, "ipa": ipa, "vi": vi, "accepted_answers": [name + "s"],
                "cefr": cefr, "x": round(0.1 + (d[2 + i] / 255) * 0.8, 3),
                "y": round(0.1 + (d[8 + i] / 255) * 0.8, 3), "confidence": 0.9,
            })
        topic = _TOPICS[d[16] % len(_TOPICS)]
        return AnalysisResult.model_validate({
            "topic": topic, "topic_tags": [topic.lower()],
            "cefr_level": "A1" if d[17] % 2 else "A2",
            "labels": labels,
            "descriptions": [
                {"en": f"A {labels[0]['name']} is here.", "vi": f"Có một {labels[0]['vi']}."},
                {"en": f"I can see a {labels[1]['name']}.", "vi": f"Tôi thấy một {labels[1]['vi']}."},
            ],
            "story": {"en": f"It is a {topic.lower()} scene. I like it.", "vi": f"Một cảnh {topic.lower()}."},
            "safety": {"is_suitable_for_students": True, "reasons": []},
        })
