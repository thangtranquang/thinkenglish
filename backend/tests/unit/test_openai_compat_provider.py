"""OpenAI-compatible LLM provider (llama.cpp / vLLM style endpoint): request shape, tolerant parsing, safety."""
import base64
import json

import httpx
import pytest

from backend.app.ai.mock import MockProvider
from backend.app.ai.openai_compat import OpenAICompatProvider
from backend.app.ai.provider import AIProviderError, select_provider
from backend.app.config import Settings
from backend.tests.helpers.images import jpeg_bytes

KEY = "sk-secret-123"
GOOD = {
    "topic": "Fruits",
    "topic_tags": ["fruit"],
    "cefr_level": "a1",
    "labels": [
        {"name": "apple", "ipa": "/ˈæp.əl/", "vi": "quả táo", "accepted_answers": ["apples"], "cefr": "A1",
         "x": 0.26, "y": 0.58, "confidence": 0.9, "bbox": [1, 2, 3, 4]},
        {"name": "Banana", "vi": "quả chuối", "x": 1.4, "y": -0.2},
        {"name": "orange", "vi": "quả cam", "x": 0.8, "y": 0.7},
        {"name": "ORANGE", "vi": "dup", "x": 0.1, "y": 0.1},
    ],
    "descriptions": [{"en": "An apple is on the plate.", "vi": "Một quả táo trên đĩa."}, "A banana is yellow."],
    "story": {"en": "I eat fruit every day. It is good.", "vi": "Mình ăn trái cây mỗi ngày."},
    "safety": {"has_identifiable_faces": False, "unexpected": 1},
}


def make(handler, key=KEY):
    return OpenAICompatProvider("https://llm.example/v1/", key, "qwen-test", timeout=5,
                                transport=httpx.MockTransport(handler))


def reply(content):
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_request_shape_and_clean_parse():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["auth"], seen["body"] = str(request.url), request.headers["authorization"], json.loads(request.content)
        return reply("```json\n" + json.dumps(GOOD) + "\n```")

    result = make(handler).analyze(jpeg_bytes(1))
    assert seen["url"] == "https://llm.example/v1/chat/completions"
    assert seen["auth"] == f"Bearer {KEY}"
    body = seen["body"]
    assert body["model"] == "qwen-test" and body["chat_template_kwargs"] == {"enable_thinking": False}
    image_part = [p for p in body["messages"][-1]["content"] if p["type"] == "image_url"][0]
    assert image_part["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert base64.b64decode(image_part["image_url"]["url"].split(",", 1)[1]) == jpeg_bytes(1)
    # tolerant parsing: duplicates dropped, coordinates clamped, unknown keys removed, strings accepted
    assert [l.name for l in result.labels] == ["apple", "Banana", "orange"]
    assert (result.labels[1].x, result.labels[1].y) == (1.0, 0.0)
    assert result.cefr_level == "A1" and result.descriptions[1].en == "A banana is yellow."
    assert result.safety.is_suitable_for_students is True


@pytest.mark.parametrize("content", ["", "no json here", '{"labels": []}', json.dumps({**GOOD, "labels": GOOD["labels"][:2]})])
def test_unusable_answers_raise_provider_error(content):
    with pytest.raises(AIProviderError):
        make(lambda r: reply(content)).analyze(jpeg_bytes(2))


def test_http_error_does_not_leak_the_key():
    with pytest.raises(AIProviderError) as exc:
        make(lambda r: httpx.Response(500, text=f"boom {KEY}")).analyze(jpeg_bytes(3))
    assert KEY not in str(exc.value) and exc.value.__cause__ is None


def test_repr_hides_the_key():
    assert KEY not in repr(make(lambda r: reply("{}")))


def test_select_provider_prefers_the_llm_endpoint():
    p = select_provider("gem-key", llm_base_url="https://llm.example/v1", llm_api_key=KEY, llm_model="m")
    assert isinstance(p, OpenAICompatProvider)
    assert isinstance(select_provider(None, llm_base_url="https://llm.example/v1", llm_api_key=""), MockProvider)


def test_settings_llm_fields_come_from_env_and_dotenv(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text('# comment\nLLM_BASE_URL="https://llm.example/v1"\nLLM_API_KEY=sk-from-file\nLLM_MODEL=file-model\n',
                      encoding="utf-8")
    s = Settings.from_env({"LLM_MODEL": "env-model"}, dotenv_path=dotenv)
    assert (s.llm_base_url, s.llm_api_key, s.llm_model) == ("https://llm.example/v1", "sk-from-file", "env-model")
    assert "sk-from-file" not in repr(s)
    assert Settings.from_env({"LLM_API_KEY": ""}, dotenv_path=dotenv).llm_api_key is None  # real env (even empty) wins
