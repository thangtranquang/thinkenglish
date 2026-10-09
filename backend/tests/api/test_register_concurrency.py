"""TC-9.1 double submit yields exactly one conversion."""
import threading

from backend.tests.conftest import register_payload


def test_double_submit_one_winner(guest, db):
    barrier, out = threading.Barrier(2), []

    def go(nick):
        barrier.wait()
        out.append(guest.post("/api/auth/register", json=register_payload(nickname=nick)).status_code)

    threads = [threading.Thread(target=go, args=(n,)) for n in ("Minh_An", "Minh_An2")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(out) == [201, 409]
    assert db.execute("SELECT COUNT(*) FROM sessions WHERE user_id = ?", (guest.user_id,)).fetchone()[0] == 1
