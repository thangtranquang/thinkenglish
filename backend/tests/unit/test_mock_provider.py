
import pytest
from pydantic import ValidationError

from backend.app.ai.gemini import GeminiProvider, box_to_center
from backend.app.ai.mock import MockProvider
from backend.app.ai.provider import select_provider
from backend.app.ai.schema import AnalysisResult
from backend.tests.helpers import images as fx


def test_call_count_and_determinism():
    p = MockProvider()
    a = p.analyze(fx.jpeg_bytes(1))
    b = p.analyze(fx.jpeg_bytes(1))
    c = p.analyze(fx.jpeg_bytes(2))
    assert p.call_count == 3
    assert a == b
    assert a != c


def test_result_valid():
    r = MockProvider().analyze(fx.jpeg_bytes(5))
    assert isinstance(r, AnalysisResult)
    assert len(r.labels) >= 3
    assert all(0 <= l.x <= 1 and 0 <= l.y <= 1 for l in r.labels)
    assert r.descriptions and r.story.en and r.safety.is_suitable_for_students


def test_schema_rejects():
    d = MockProvider().analyze(fx.jpeg_bytes(1)).model_dump()
    bad = dict(d, labels=d["labels"][:2])
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate(bad)
    bad = dict(d, extra_field=1)
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate(bad)
    labels = [dict(l) for l in d["labels"]]
    labels[0]["x"] = 1.5
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate(dict(d, labels=labels))


def test_script_hook_failure():
    def script(n, data):
        if n == 1:
            raise RuntimeError("boom")
        return None

    p = MockProvider(script=script)
    with pytest.raises(RuntimeError):
        p.analyze(fx.jpeg_bytes(1))
    assert p.analyze(fx.jpeg_bytes(1)).labels
    assert p.call_count == 2


def test_delay_and_block_hooks_inert_by_default():
    p = MockProvider()
    assert p.delay == 0 and p.block_on is None and p.script is None
    assert p.max_concurrency == 0


def test_block_on_event():
    import threading

    ev = threading.Event()
    p = MockProvider(block_on=ev)
    out = []
    t = threading.Thread(target=lambda: out.append(p.analyze(fx.jpeg_bytes(1))))
    t.start()
    t.join(0.2)
    assert t.is_alive()
    ev.set()
    t.join(2)
    assert out and p.max_concurrency == 1


def test_select_provider():
    assert isinstance(select_provider(None), MockProvider)
    assert isinstance(select_provider(""), MockProvider)
    g = select_provider("k-secret")
    assert isinstance(g, GeminiProvider)
    assert "k-secret" not in repr(g)


def test_box_to_center():
    assert box_to_center([480, 380, 620, 520]) == (0.45, 0.55)
    with pytest.raises(ValueError):
        box_to_center([0, 0, 2000, 10])
