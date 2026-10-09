"""Garbage collection helpers shared by account deletion and maintenance."""
from __future__ import annotations

import sqlite3
from datetime import timedelta
from pathlib import Path

from ..clock import Clock, iso
from ..config import Settings
from ..repositories import maintenance as repo

CLAIM_DAYS = 7
STRAY_FILE_AGE = timedelta(days=1)


def _resolve(base: Path, storage_path: str) -> Path:
    return (base / storage_path).resolve()


def gc_orphans(conn: sqlite3.Connection, clock: Clock) -> list[str]:
    """Delete orphan contents + image rows (caller owns the transaction). Returns storage paths to unlink."""
    cutoff = iso(clock.now() - timedelta(days=CLAIM_DAYS))
    paths = []
    for o in repo.orphan_contents(conn, cutoff):
        repo.delete_content_and_asset(conn, o["content_id"], o["asset_id"])
        paths.append(o["storage_path"])
    return paths


def unlink_files(settings: Settings, storage_paths: list[str]) -> int:
    base = Path(settings.data_dir).resolve()
    removed = 0
    for sp in storage_paths:
        target = _resolve(base, sp)
        if base in target.parents and target.is_file():
            target.unlink()
            removed += 1
    return removed


def sweep_stray_files(conn: sqlite3.Connection, clock: Clock, settings: Settings) -> int:
    """Remove files under data/images that no image_assets row references and that are over a day old."""
    base = Path(settings.data_dir).resolve()
    images = base / "images"
    if not images.is_dir():
        return 0
    known = {_resolve(base, p) for p in repo.all_storage_paths(conn)}
    limit = (clock.now() - STRAY_FILE_AGE).timestamp()
    removed = 0
    for f in images.rglob("*"):
        if f.is_file() and f.resolve() not in known and f.stat().st_mtime < limit:
            f.unlink()
            removed += 1
    return removed
