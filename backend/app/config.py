"""Settings read from the environment. No secrets in code; everything is overridable for tests."""
import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    app_origin: str = "http://localhost:8000"
    data_dir: Path = ROOT / "data"
    db_path: Path = ROOT / "data" / "reflex.db"
    gemini_api_key: str | None = field(default=None, repr=False)
    session_idle_seconds: int = 1800
    guest_free_sessions: int = 1
    login_fail_per_nickname: int = 5
    login_fail_per_ip: int = 100
    login_window_seconds: int = 900
    register_per_ip: int = 30
    register_window_seconds: int = 3600
    guest_create_per_ip_per_hour: int = 60
    max_upload_bytes: int = 5 * 1024 * 1024
    max_pixels: int = 25_000_000
    processing_stale_seconds: int = 120
    scrypt_n: int = 2**14

    @property
    def is_local(self) -> bool:
        """True on localhost, where cookies cannot be Secure."""
        return urlsplit(self.app_origin).hostname in {"localhost", "127.0.0.1", "::1"}

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if env is None else env
        values: dict = {}
        for f in fields(cls):
            raw = env.get(f.name.upper())
            if raw is None or raw == "":
                continue
            if f.name in ("data_dir", "db_path"):
                values[f.name] = Path(raw)
            elif f.type is int or f.type == "int":
                values[f.name] = int(raw)
            else:
                values[f.name] = raw
        if "data_dir" in values and "db_path" not in values:
            values["db_path"] = values["data_dir"] / "reflex.db"
        return cls(**values)
