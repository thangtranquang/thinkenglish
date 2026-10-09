"""Public endpoints: health and client config (never any secret)."""
from fastapi import APIRouter, Request

from ..schemas.common import ConfigOut, HealthOut

router = APIRouter(prefix="/api")

AVATARS = ["fox", "panda", "tiger", "frog", "owl", "octopus"]
CEFR_LEVELS = ["A1", "A2", "B1"]
MIN_AGE = 10
MAX_AGE = 100


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(status="ok")


@router.get("/config", response_model=ConfigOut)
def config(request: Request) -> ConfigOut:
    s = request.app.state.settings
    year = request.app.state.clock.now().year  # UTC year; the age rule itself lives in validators
    return ConfigOut(
        avatars=AVATARS,
        cefr_levels=CEFR_LEVELS,
        max_upload_bytes=s.max_upload_bytes,
        max_pixels=s.max_pixels,
        guest_free_sessions=s.guest_free_sessions,
        session_idle_seconds=s.session_idle_seconds,
        birth_year_min=year - MAX_AGE,
        birth_year_max=year - MIN_AGE,
    )
