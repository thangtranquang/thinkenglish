"""App factory. `create_app(settings, clock=..., provider=...)` is what tests use."""
import importlib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .clock import Clock, SystemClock
from .config import Settings
from .db import connect, init_db
from .errors import install_error_handlers
from .middleware import SecurityHeadersMiddleware
from .routers import auth, cards, health_config, me, practice, session, uploads
from .seed import seed_all

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


def _run_maintenance_once(settings: Settings, clock: Clock) -> None:
    """Call maintenance if that module exists yet (it arrives in a later slice)."""
    try:
        module = importlib.import_module("backend.app.maintenance")
    except ModuleNotFoundError as exc:
        if exc.name != "backend.app.maintenance":
            raise
        return
    conn = connect(settings.db_path)
    try:
        module.run_maintenance(conn, clock, settings)
    finally:
        conn.close()


def create_app(settings: Settings | None = None, *, clock: Clock | None = None,
               provider=None) -> FastAPI:
    settings = settings or Settings.from_env()
    clock = clock or SystemClock()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        init_db(settings.db_path, clock)
        conn = connect(settings.db_path)
        try:
            seed_all(conn, settings, clock)
        finally:
            conn.close()
        _run_maintenance_once(settings, clock)
        yield

    app = FastAPI(title="ReflexEnglish", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings, app.state.clock, app.state.provider = settings, clock, provider
    install_error_handlers(app)
    app.add_middleware(SecurityHeadersMiddleware)

    for module in (health_config, session, auth, me, cards, uploads, practice):
        app.include_router(module.router)

    FRONTEND_DIR.mkdir(exist_ok=True)
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    return app


app = create_app()
