"""TC-35.1 pragmas, TC-35.3 seed, TC-35.18 cascades, migration idempotence."""
import uuid

from backend.app.db import connect, init_db
from backend.app.seed import SEED_NAMESPACE, seed_all


def _fresh_db(settings, clock):
    init_db(settings.db_path, clock)
    return connect(settings.db_path)


def _fk_actions(conn, table):
    return {(r[3], r[2]): r[6] for r in conn.execute(f"PRAGMA foreign_key_list({table})")}


def test_pragmas_on_every_connection(settings, clock):
    init_db(settings.db_path, clock)
    for _ in range(3):
        conn = connect(settings.db_path)
        try:
            assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
            assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
            assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
            assert conn.execute("PRAGMA synchronous").fetchone()[0] == 1
        finally:
            conn.close()


def test_init_db_twice_leaves_one_migration_row(settings, clock):
    init_db(settings.db_path, clock)
    init_db(settings.db_path, clock)
    conn = connect(settings.db_path)
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    conn.close()
    assert len(rows) == 1


def test_seed_counts_and_stable_ids(settings, clock):
    conn = _fresh_db(settings, clock)
    seed_all(conn, settings, clock)

    def counts():
        return {
            t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("users", "cards", "card_contents", "card_labels", "card_sentences", "image_assets")
        }

    first = counts()
    ids = [r[0] for r in conn.execute("SELECT id FROM cards ORDER BY id")]
    seed_all(conn, settings, clock)  # idempotent
    assert counts() == first
    assert [r[0] for r in conn.execute("SELECT id FROM cards ORDER BY id")] == ids

    assert first == {
        "users": 1, "cards": 7, "card_contents": 7,
        "card_labels": 21, "card_sentences": 21, "image_assets": 7,
    }
    assert str(uuid.uuid5(SEED_NAMESPACE, "c1:card")) in ids
    assert conn.execute("SELECT kind FROM users").fetchone()[0] == "system"
    bad = conn.execute(
        "SELECT COUNT(*) FROM cards c JOIN card_contents cc ON cc.id = c.content_id "
        "WHERE c.visibility != 'public' OR cc.moderation_status != 'approved' OR cc.status != 'ready'"
    ).fetchone()[0]
    assert bad == 0
    assert conn.execute("SELECT COUNT(*) FROM card_labels WHERE audio_file IS NULL").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM card_sentences WHERE audio_file IS NULL").fetchone()[0] == 0
    assert conn.execute("SELECT audio_file FROM card_labels WHERE word = 'cup'").fetchone()[0] == "cup-b88678d.mp3"
    conn.close()


def test_every_user_owned_table_cascades(settings, clock):
    conn = _fresh_db(settings, clock)
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    checked = 0
    for t in tables:
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({t})")}
        fks = _fk_actions(conn, t)
        for col in ("user_id", "owner_id"):
            if col in cols:
                assert fks.get((col, "users")) == "CASCADE", f"{t}.{col}"
                checked += 1
    assert checked >= 9
    assert _fk_actions(conn, "image_assets")[("first_uploaded_by", "users")] == "SET NULL"
    for t in ("card_progress", "card_saves"):
        assert _fk_actions(conn, t)[("card_id", "cards")] == "CASCADE"
    assert _fk_actions(conn, "cards")[("content_id", "card_contents")] == "RESTRICT"
    conn.close()
