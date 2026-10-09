"""TC-40.4: the clock is injectable; no direct wall-clock calls outside clock.py."""
import re
from datetime import datetime, timezone
from pathlib import Path

from backend.app.clock import FakeClock
from backend.app.db import connect, init_db
from backend.app.seed import seed_all

APP = Path(__file__).resolve().parents[2] / "app"
FORBIDDEN = re.compile(r"datetime\.(now|utcnow|today)\s*\(|\btime\.time\s*\(|\bdate\.today\s*\(")


def test_no_direct_wall_clock_calls_outside_clock_module():
    offenders = []
    for p in APP.rglob("*.py"):
        if p.name == "clock.py":
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if FORBIDDEN.search(line):
                offenders.append(f"{p.relative_to(APP)}:{i}")
    assert offenders == []


def test_scenario_is_deterministic_with_fake_clock(settings):
    stamp = datetime(2026, 3, 1, 12, 30, tzinfo=timezone.utc)
    clock = FakeClock(stamp)
    init_db(settings.db_path, clock)
    conn = connect(settings.db_path)
    seed_all(conn, settings, clock)
    created = conn.execute("SELECT created_at FROM users").fetchone()[0]
    conn.close()
    assert created.startswith("2026-03-01T12:30:00")
    clock.advance(seconds=1801)
    assert clock.now() == datetime(2026, 3, 1, 13, 0, 1, tzinfo=timezone.utc)
