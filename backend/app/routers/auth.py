"""Register, login, logout, logout-all."""
from fastapi import APIRouter, Depends, Request, Response

from .. import deps
from ..errors import AppError
from ..repositories import users
from ..schemas.auth import LoginIn, RegisterIn
from ..schemas.session import MeOut
from ..services import auth as auth_service
from ..services import practice as practice_service
from . import health_config

router = APIRouter(prefix="/api/auth")


def _register_limit(request: Request, _csrf: None = Depends(deps.csrf), conn=Depends(deps.get_conn)) -> None:
    """Every request that passed CSRF counts (422/409 included); 429s are not counted."""
    s, clock, ip = deps.settings_of(request), deps.clock_of(request), deps.client_ip(request)
    auth_service.check_limit(conn, clock, s, "register_ip", ip)
    auth_service.record_event(conn, clock, "register_ip", ip)


def _open_session(response: Response, settings, token: str) -> None:
    deps.set_cookie(response, settings, deps.SESSION_COOKIE, token, deps.SESSION_COOKIE_DAYS)
    deps.clear_cookie(response, settings, deps.DEVICE_COOKIE)


@router.post("/register", response_model=MeOut, status_code=201)
def register(data: RegisterIn, request: Request, response: Response, _limit: None = Depends(_register_limit),
             user: deps.CurrentUser | None = Depends(deps.optional_identity),
             conn=Depends(deps.get_conn)) -> MeOut:
    settings, clock = deps.settings_of(request), deps.clock_of(request)
    if user is None:
        # A cookie that no longer maps to a guest was just converted (double submit) or retired.
        if request.cookies.get(deps.DEVICE_COOKIE) or request.cookies.get(deps.SESSION_COOKIE):
            raise AppError(409, "already_registered")
        raise AppError(401, "no_session")
    token = auth_service.register(conn, clock, settings, user.row, data, health_config.AVATARS)
    _open_session(response, settings, token)
    row = users.get(conn, user.id)
    return MeOut.from_row(row, practice_service.profile_stats(conn, clock, row["id"]))


@router.post("/login", response_model=MeOut)
def login(data: LoginIn, request: Request, response: Response, _csrf: None = Depends(deps.csrf),
          current: deps.CurrentUser | None = Depends(deps.optional_identity),
          conn=Depends(deps.get_conn)) -> MeOut:
    settings, clock = deps.settings_of(request), deps.clock_of(request)
    row, token = auth_service.login(conn, clock, settings, current.row if current else None, data,
                                    deps.client_ip(request))
    auth_service.logout(conn, clock, request.cookies.get(deps.SESSION_COOKIE))  # retire the old session
    _open_session(response, settings, token)
    return MeOut.from_row(row, practice_service.profile_stats(conn, clock, row["id"]))


@router.post("/logout", status_code=204)
def logout(request: Request, _csrf: None = Depends(deps.csrf), conn=Depends(deps.get_conn)) -> Response:
    settings = deps.settings_of(request)
    auth_service.logout(conn, deps.clock_of(request), request.cookies.get(deps.SESSION_COOKIE))
    response = Response(status_code=204)
    deps.clear_cookie(response, settings, deps.SESSION_COOKIE)
    return response


@router.post("/logout-all", status_code=204)
def logout_all(request: Request, user: deps.CurrentUser = Depends(deps.registered_user("account")),
               conn=Depends(deps.get_conn)) -> Response:
    auth_service.logout_all(conn, deps.clock_of(request), user.id)
    response = Response(status_code=204)
    deps.clear_cookie(response, deps.settings_of(request), deps.SESSION_COOKIE)
    return response
