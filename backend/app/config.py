"""Settings read from the environment. No secrets in code; everything is overridable for tests."""
import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]


def read_dotenv(path: Path) -> dict[str, str]:
    """Minimal KEY=VALUE parser (comments, optional quotes); a missing file gives an empty dict."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("\"'")
    return values


@dataclass(frozen=True)
class Settings:
    app_origin: str = "http://localhost:8000"
    data_dir: Path = ROOT / "data"
    db_path: Path = ROOT / "data" / "reflex.db"
    gemini_api_key: str | None = field(default=None, repr=False)
    llm_base_url: str | None = None  # OpenAI-compatible endpoint, e.g. https://host/v1
    llm_api_key: str | None = field(default=None, repr=False)
    llm_model: str = "qwen3.6-35b-a3b"
    llm_timeout_seconds: int = 120
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
    def from_env(cls, env: Mapping[str, str] | None = None, dotenv_path: Path | None = None) -> "Settings":
        """Real environment variables win over the optional `.env` file (an empty value counts as set)."""
        if env is None:
            env = {**read_dotenv(dotenv_path or ROOT / ".env"), **os.environ}
        elif dotenv_path is not None:
            env = {**read_dotenv(dotenv_path), **env}
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
