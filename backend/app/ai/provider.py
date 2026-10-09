"""AIProvider interface and selection. Only services/upload may call a provider."""
from __future__ import annotations

from typing import Protocol

from .schema import AnalysisResult


class AIProviderError(Exception):
    """Provider failed (network, bad response, invalid schema)."""


class AIProvider(Protocol):
    def analyze(self, image_bytes: bytes) -> AnalysisResult: ...


def select_provider(api_key: str | None) -> AIProvider:
    if api_key and api_key.strip():
        from .gemini import GeminiProvider

        return GeminiProvider(api_key.strip())
    from .mock import MockProvider

    return MockProvider()
