"""Account deletion: verified password, FK cascade, then orphan GC of contents and files."""
from __future__ import annotations

import sqlite3

from ..clock import Clock
from ..config import Settings
from ..db import transaction
from ..errors import AppError
from ..repositories import users
from ..security import verify_password
from . import auth as auth_service
from . import maintenance as gc


def delete_account(conn: sqlite3.Connection, clock: Clock, settings: Settings, user: dict, password: str,
                   ip: str) -> None:
    auth_service.check_login_limits(conn, clock, settings, user["nickname"], ip)
    if not verify_password(password, user["password_hash"], user["password_params"]):
        auth_service.record_login_failure(conn, clock, user["nickname"], ip)
        raise AppError(403, "invalid_credentials")
    with transaction(conn):
        users.delete(conn, user["id"])
        paths = gc.gc_orphans(conn, clock)
    gc.unlink_files(settings, paths)
