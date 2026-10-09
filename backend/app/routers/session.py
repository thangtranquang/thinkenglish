"""Bootstrap (create/recognise the browser's identity) and heartbeat."""
from fastapi import APIRouter, Depends, Request, Response

from .. import deps
from ..schemas.session import BootstrapOut, HeartbeatOut, MeOut
from ..services import auth as auth_service
from ..services import identity as identity_service
from ..services import practice as practice_service
from . import health_config

router = APIRouter(prefix="/api/session")


@router.post("/bootstrap", response_model=BootstrapOut)
def bootstrap(request: Request, response: Response, _origin: None = Depends(deps.origin_guard),
              conn=Depends(deps.get_conn)) -> BootstrapOut:
    settings, clock = deps.settings_of(request), deps.clock_of(request)
    found = identity_service.resolve(conn, clock.now(), request.cookies.get(deps.SESSION_COOKIE),
                                     request.cookies.get(deps.DEVICE_COOKIE))
    if found is None:
        ip = deps.client_ip(request)
        auth_service.check_limit(conn, clock, settings, "guest_ip", ip)
        row, device_token, _ = identity_service.create_guest(conn, clock)
        auth_service.record_event(conn, clock, "guest_ip", ip)
        deps.set_cookie(response, settings, deps.DEVICE_COOKIE, device_token, deps.DEVICE_COOKIE_DAYS)
    else:
        row, _ = identity_service.touch_usage(conn, clock, settings, found)
    if (found is None or found.via != "session") and request.cookies.get(deps.SESSION_COOKIE):
        deps.clear_cookie(response, settings, deps.SESSION_COOKIE)  # dead session cookie: reveal nothing
    csrf_token = deps.ensure_csrf_cookie(request, response)
    me = MeOut.from_row(row, practice_service.profile_stats(conn, clock, row["id"]))
    return BootstrapOut(**me.model_dump(), csrf_token=csrf_token, config=health_config.config(request))


@router.post("/heartbeat", response_model=HeartbeatOut)
def heartbeat(user: deps.CurrentUser = Depends(deps.current_user)) -> HeartbeatOut:
    return HeartbeatOut(gate=MeOut.from_row(user.row).gate)
