"""TC-34.1, 34.4, 34.16 and the CLI: purge, GC and idempotence."""
import os
import subprocess
import sys
from datetime import timedelta

from backend.app.clock import iso
from backend.app.maintenance import run_maintenance
from backend.app.seed import SYSTEM_USER_ID
from backend.tests.helpers.practice import insert_card, insert_claim, insert_content


def _guest(db, clock, uid, last_seen_days, wrote=True):
    stamp = iso(clock.now() - timedelta(days=last_seen_days))
    db.execute("INSERT INTO users (id, kind, cefr_level, created_at, last_seen_at) VALUES (?, 'guest', 'A1', ?, ?)",
               (uid, stamp, stamp))
    db.execute("INSERT INTO usage_sessions (id, user_id, started_at, last_activity_at, had_write) "
               "VALUES (?, ?, ?, ?, ?)", ("s-" + uid, uid, stamp, stamp, 1 if wrote else 0))


def _count(db, table):
    return db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]


def _has(db, content):
    return db.execute("SELECT COUNT(*) FROM card_contents WHERE id = ?", (content["content_id"],)).fetchone()[0]


def test_purges_idle_guests_and_is_idempotent(reg, db, clock, settings):  # TC-34.1, 34.4
    _guest(db, clock, "old-guest", 181)
    _guest(db, clock, "recent-guest", 10)
    _guest(db, clock, "empty-guest", 8, wrote=False)
    db.execute("INSERT INTO rate_events (bucket, key_hash, created_at) VALUES ('login_ip', 'x', ?)",
               (iso(clock.now() - timedelta(days=2)),))
    first = run_maintenance(db, clock, settings)
    ids = {r[0] for r in db.execute("SELECT id FROM users")}
    assert "old-guest" not in ids and "empty-guest" not in ids and "recent-guest" in ids
    assert reg.user_id in ids and SYSTEM_USER_ID in ids
    assert first["idle_guests"] == 1 and first["empty_guests"] == 1 and first["rate_events"] == 1
    tables = ("users", "card_contents", "image_assets", "rate_events")
    snapshot = {t: _count(db, t) for t in tables}
    run_maintenance(db, clock, settings)
    assert snapshot == {t: _count(db, t) for t in tables}


def test_gc_keeps_referenced_seed_and_claimed_content(reg, db, clock, settings):  # TC-34.16
    d = settings.data_dir
    now = clock.now()
    old, fresh = iso(now - timedelta(days=30)), iso(now - timedelta(days=1))
    referenced = insert_content(db, d)
    insert_card(db, reg.user_id, referenced["content_id"])
    seed = insert_content(db, d, seed_key="zz")
    orphan = insert_content(db, d)
    claimed = insert_content(db, d)
    insert_claim(db, reg.user_id, claimed["content_id"], fresh)
    stale_claim = insert_content(db, d)
    insert_claim(db, reg.user_id, stale_claim["content_id"], old)
    stray = d / "images" / "zz" / "zz" / "stray.jpg"
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_bytes(b"x")
    os.utime(stray, (0, 0))
    stale_proc = insert_content(db, d, status="processing")
    db.execute("UPDATE card_contents SET processing_started_at = ? WHERE id = ?", (old, stale_proc["content_id"]))
    insert_claim(db, reg.user_id, stale_proc["content_id"], fresh)
    run_maintenance(db, clock, settings)
    assert _has(db, referenced) and _has(db, seed) and _has(db, claimed) and _has(db, stale_proc)
    assert not _has(db, orphan) and not _has(db, stale_claim)
    assert referenced["path"].exists() and seed["path"].exists() and claimed["path"].exists()
    assert not orphan["path"].exists() and not stale_claim["path"].exists() and not stray.exists()
    status = db.execute("SELECT status FROM card_contents WHERE id = ?", (stale_proc["content_id"],)).fetchone()[0]
    assert status == "failed"
    left = db.execute("SELECT COUNT(*) FROM upload_claims WHERE content_id = ?",
                      (stale_claim["content_id"],)).fetchone()[0]
    assert left == 0


def test_cli_exits_zero_twice(tmp_path):
    env = {**os.environ, "DATA_DIR": str(tmp_path / "cli-data")}
    for _ in range(2):
        r = subprocess.run([sys.executable, "-m", "backend.app.maintenance"], env=env, capture_output=True,
                           text=True)
        assert r.returncode == 0, r.stderr
        assert r.stdout.startswith("maintenance:")
