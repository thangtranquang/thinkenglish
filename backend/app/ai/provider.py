"""AIProvider interface and selection. Only services/upload may call a provider."""
from __future__ import annotations

from typing import Protocol

from .schema import AnalysisResult


class AIProviderError(Exception):
    """Provider failed (network, bad response, invalid schema)."""


class AIProvider(Protocol):
    def analyze(self, image_bytes: bytes) -> AnalysisResult: ...


def select_provider(api_key: str | None = None, *, llm_base_url: str | None = None,
                    llm_api_key: str | None = None, llm_model: str = "qwen3.6-35b-a3b",
                    llm_timeout: float = 120.0) -> AIProvider:
    """OpenAI-compatible LLM endpoint first, then Gemini, else the deterministic mock."""
    if llm_base_url and llm_base_url.strip() and llm_api_key and llm_api_key.strip():
        from .openai_compat import OpenAICompatProvider

        return OpenAICompatProvider(llm_base_url.strip(), llm_api_key.strip(), llm_model, llm_timeout)
    if api_key and api_key.strip():
        from .gemini import GeminiProvider

        return GeminiProvider(api_key.strip())
    from .mock import MockProvider

    return MockProvider()
