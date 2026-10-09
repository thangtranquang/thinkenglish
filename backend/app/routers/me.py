"""GET/PATCH /api/me, PUT /api/me/settings, DELETE /api/me."""
from fastapi import APIRouter, Depends, Request, Response

from .. import deps
from ..errors import AppError
from ..schemas.me import DeleteMeIn, MePatchIn, SettingsIn
from ..schemas.session import MeOut
from ..services import account
from ..services import practice as practice_service
from . import health_config

router = APIRouter(prefix="/api")


def me_out(user: deps.CurrentUser, request: Request) -> dict:
    row = account.get_user(user.conn, user.id)
    stats = practice_service.profile_stats(user.conn, deps.clock_of(request), user.id)
    out = MeOut.from_row(row, stats).model_dump()
    out["settings"] = {"hide_timer": bool(row["hide_timer"])}
    out["mastery"] = practice_service.mastery_summary(user.conn, user.id)
    return out


@router.get("/me")
def me(request: Request, user: deps.CurrentUser = Depends(deps.current_user)) -> dict:
    return me_out(user, request)


@router.patch("/me")
def patch_me(data: MePatchIn, request: Request,
             user: deps.CurrentUser = Depends(deps.registered_user("profile"))) -> dict:
    if data.avatar_key is not None and data.avatar_key not in health_config.AVATARS:
        raise AppError(422, "validation_error", fields={"avatar_key": "unknown avatar"})
    account.update_profile(user.conn, user.id, data.avatar_key, data.cefr_level)
    return me_out(user, request)


@router.put("/me/settings")
def put_settings(data: SettingsIn, user: deps.CurrentUser = Depends(deps.not_gated_user)) -> dict:
    account.set_hide_timer(user.conn, user.id, data.hide_timer)
    return {"hide_timer": data.hide_timer}


@router.delete("/me", status_code=204)
def delete_me(data: DeleteMeIn, request: Request,
              user: deps.CurrentUser = Depends(deps.registered_user("account"))) -> Response:
    settings = deps.settings_of(request)
    account.delete_account(user.conn, deps.clock_of(request), settings, user.row, data.password,
                           deps.client_ip(request))
    response = Response(status_code=204)
    for name in (deps.SESSION_COOKIE, deps.DEVICE_COOKIE):
        deps.clear_cookie(response, settings, name)
    deps.clear_cookie(response, settings, deps.csrf_cookie_name(settings), http_only=False)
    return response
