"""Periodic cleanup. ``run_maintenance`` is idempotent; also runnable as ``python -m backend.app.maintenance``."""
from __future__ import annotations

import sqlite3
import sys
from datetime import timedelta

from .clock import Clock, SystemClock, iso
from .config import Settings
from .db import connect, init_db, transaction
from .repositories import maintenance as repo
from .services import maintenance as gc

IDLE_GUEST_DAYS = 180
EMPTY_GUEST_DAYS = 7
CLAIM_DAYS = 7


def run_maintenance(conn: sqlite3.Connection, clock: Clock, settings: Settings) -> dict[str, int]:
    now = clock.now()
    counts: dict[str, int] = {}
    with transaction(conn):
        counts["idle_guests"] = repo.delete_idle_guests(conn, iso(now - timedelta(days=IDLE_GUEST_DAYS)))
        counts["empty_guests"] = repo.delete_never_wrote_guests(conn, iso(now - timedelta(days=EMPTY_GUEST_DAYS)))
        counts["stale_processing"] = repo.fail_stale_processing(
            conn, iso(now - timedelta(seconds=settings.processing_stale_seconds)))
        counts["stale_claims"] = repo.delete_stale_claims(conn, iso(now - timedelta(days=CLAIM_DAYS)))
        paths = gc.gc_orphans(conn, clock)
        counts["orphan_contents"] = len(paths)
        counts["rate_events"] = repo.delete_old_rate_events(conn, iso(now - timedelta(days=1)))
    counts["files_removed"] = gc.unlink_files(settings, paths, conn) + gc.sweep_stray_files(conn, clock, settings)
    return counts


def main() -> int:
    settings, clock = Settings.from_env(), SystemClock()
    init_db(settings.db_path, clock)
    conn = connect(settings.db_path)
    try:
        counts = run_maintenance(conn, clock, settings)
    finally:
        conn.close()
    print("maintenance: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
