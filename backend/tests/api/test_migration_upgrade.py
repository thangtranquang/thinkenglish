"""A database created before migration 002 must upgrade in place (bootstrap used to 500 on old DBs)."""
import shutil
import sqlite3

import pytest

from backend.app import db

INSERT = "INSERT INTO rate_events (bucket, key_hash, created_at) VALUES (?, 'k', '2026-01-01T00:00:00Z')"


def test_old_database_upgrades_and_keeps_events(tmp_path, monkeypatch, clock):
    real = db.MIGRATIONS_DIR
    old = tmp_path / "old_migrations"
    old.mkdir()
    shutil.copy(real / "001_init.sql", old / "001_init.sql")
    path = tmp_path / "old.db"

    monkeypatch.setattr(db, "MIGRATIONS_DIR", old)
    db.init_db(path, clock)
    conn = sqlite3.connect(path)
    conn.execute(INSERT, ("login_ip",))
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):  # the old schema has no guest_ip bucket
        conn.execute(INSERT, ("guest_ip",))
    conn.close()

    monkeypatch.setattr(db, "MIGRATIONS_DIR", real)
    db.init_db(path, clock)
    db.init_db(path, clock)  # idempotent
    conn = sqlite3.connect(path)
    conn.execute(INSERT, ("guest_ip",))
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM rate_events").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 2
    conn.close()
