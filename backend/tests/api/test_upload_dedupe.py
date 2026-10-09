"""TC-21.1, TC-21.3: AI is called once per unique image."""
from backend.app.ai.mock import MockProvider
from backend.tests.conftest import register_payload
from backend.tests.helpers.images import jpeg_bytes
from backend.tests.helpers.threads import run_together
from backend.tests.helpers.uploads import ready_content, upload


def _second(new_api):
    api = new_api()
    assert api.post("/api/auth/register", json=register_payload(nickname="Bao_Chau")).status_code == 201
    return api


def test_second_user_gets_ready_content(reg, new_api, provider, db):
    data = jpeg_bytes(5)
    ready_content(reg, data)
    b = _second(new_api)
    r = upload(b, data)
    assert r.status_code == 202
    assert r.json()["dedupe"] == "ready" and r.json()["status"] == "ready" and r.json()["ai_calls"] == 1
    assert provider.call_count == 1
    assert db.execute("SELECT COUNT(*) FROM upload_claims").fetchone()[0] == 2
    n = db.execute("SELECT COUNT(*) FROM cards WHERE owner_id IN (?, ?)", (reg.user_id, b.user_id)).fetchone()[0]
    assert n == 0


def test_simultaneous_identical_uploads_call_provider_once(reg, new_api, app, db):
    provider = MockProvider(delay=0.3)
    app.state.provider = provider
    b = _second(new_api)
    data = jpeg_bytes(9)
    rs = run_together([lambda: upload(reg, data), lambda: upload(b, data)])
    assert {r.status_code for r in rs} == {202}
    assert [r.json()["dedupe"] for r in rs].count("none") == 1
    assert provider.call_count == 1
    assert db.execute("SELECT ai_calls FROM card_contents WHERE seed_key IS NULL").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM upload_claims").fetchone()[0] == 2
