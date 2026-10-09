"""Models shared by several routers."""
from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Base for every request model: unknown fields are rejected."""
    model_config = ConfigDict(extra="forbid")


class HealthOut(BaseModel):
    status: str


class ConfigOut(BaseModel):
    avatars: list[str]
    cefr_levels: list[str]
    max_upload_bytes: int
    max_pixels: int
    guest_free_sessions: int
    session_idle_seconds: int
    birth_year_min: int
    birth_year_max: int
